from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from fruit_agent.app import app
from fruit_agent.config import Settings
from fruit_agent.db import SessionFactory, engine
from fruit_agent.demo.constants import DEMO_TENANT_ID, DEMO_USERS
from fruit_agent.identity.models import Membership, Role, Tenant, User


def _settings(tmp_path: Path, *, enabled: bool) -> Settings:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "demo-private.pem"
    public_path = tmp_path / "demo-public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return Settings(
        environment="development",
        demo_mode=enabled,
        demo_private_key_path=str(private_path),
        demo_public_key_path=str(public_path),
    )


@pytest.fixture
async def migrated_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


async def _seed_operator() -> None:
    valid_until = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as session:
        session.add(
            Tenant(
                id=DEMO_TENANT_ID,
                name="果序生鲜（华东）",
                valid_until=valid_until,
            )
        )
        session.add(
            User(
                id=DEMO_USERS[Role.operator],
                tenant_id=DEMO_TENANT_ID,
                email="operator@demo.fruit-agent.local",
                valid_until=valid_until,
            )
        )
        await session.flush()
        session.add(
            Membership(
                tenant_id=DEMO_TENANT_ID,
                user_id=DEMO_USERS[Role.operator],
                role=Role.operator.value,
                valid_until=valid_until,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_demo_session_is_hidden_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "fruit_agent.demo.router.get_settings",
        lambda: _settings(tmp_path, enabled=False),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/demo/session",
            json={"role": "owner"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_demo_session_refuses_an_unseeded_role(
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del migrated_database
    monkeypatch.setattr(
        "fruit_agent.demo.router.get_settings",
        lambda: _settings(tmp_path, enabled=True),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/demo/session",
            json={"role": "owner"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "demo data is not seeded"


@pytest.mark.asyncio
async def test_demo_session_uses_only_a_seeded_active_member(
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del migrated_database
    await _seed_operator()
    monkeypatch.setattr(
        "fruit_agent.demo.router.get_settings",
        lambda: _settings(tmp_path, enabled=True),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/demo/session",
            json={"role": "operator"},
        )

    assert response.status_code == 201
    assert response.json()["role"] == "operator"
    assert response.json()["access_token"]
    assert response.json()["expires_at"]
