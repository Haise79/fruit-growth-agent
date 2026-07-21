from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from fruit_agent.config import Settings
from fruit_agent.db import SessionFactory, engine
from fruit_agent.demo.constants import DEMO_TENANT_ID
from fruit_agent.demo.seed import DemoSeedRefused, seed_demo
from fruit_agent.identity.models import Tenant


@pytest.fixture
async def migrated_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


def _settings(tmp_path: Path, *, environment: str = "development") -> Settings:
    return Settings(
        environment=environment,
        demo_mode=True,
        demo_private_key_path=str(tmp_path / "demo" / "rs256-private.pem"),
        demo_public_key_path=str(tmp_path / "demo" / "rs256-public.pem"),
    )


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_preserves_other_tenants(
    migrated_database: None,
    tmp_path: Path,
) -> None:
    del migrated_database
    other_tenant_id = uuid4()
    valid_until = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as session:
        session.add(
            Tenant(
                id=other_tenant_id,
                name="不得修改",
                valid_until=valid_until,
            )
        )
        await session.commit()

    settings = _settings(tmp_path)
    first = await seed_demo(SessionFactory, settings)
    second = await seed_demo(SessionFactory, settings)

    assert first == second
    assert second.tenants == 1
    assert second.members == 4
    assert second.skus == 6
    assert second.knowledge == 8
    assert second.approvals == 4
    assert second.cases == 5
    assert Path(settings.demo_private_key_path).is_file()
    assert Path(settings.demo_public_key_path).is_file()

    async with SessionFactory() as session:
        other_tenant = await session.scalar(
            select(Tenant).where(Tenant.id == other_tenant_id)
        )
        demo_tenant = await session.scalar(
            select(Tenant).where(Tenant.id == DEMO_TENANT_ID)
        )
    assert other_tenant is not None
    assert other_tenant.name == "不得修改"
    assert demo_tenant is not None
    assert demo_tenant.name == "果序生鲜（华东）"


@pytest.mark.asyncio
async def test_seed_refuses_non_development_environment(tmp_path: Path) -> None:
    with pytest.raises(DemoSeedRefused, match="development"):
        await seed_demo(SessionFactory, _settings(tmp_path, environment="production"))
