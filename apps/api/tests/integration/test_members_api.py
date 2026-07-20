from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.db import SessionFactory, engine, get_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Membership, Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal


@pytest.fixture
async def migrated_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
async def seeded_members(
    migrated_database: None,
) -> tuple[UUID, UUID, UUID, UUID]:
    del migrated_database
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    actor_id = uuid4()
    tenant_b_user_id = uuid4()
    tenant_b_membership_id = uuid4()

    async with SessionFactory() as session:
        valid_until = datetime.now(UTC) + timedelta(days=30)
        session.add_all(
            [
                Tenant(id=tenant_a_id, name="Tenant A", valid_until=valid_until),
                Tenant(id=tenant_b_id, name="Tenant B", valid_until=valid_until),
                User(
                    id=actor_id,
                    tenant_id=tenant_a_id,
                    email="owner-a@example.com",
                    valid_until=valid_until,
                ),
                User(
                    id=tenant_b_user_id,
                    tenant_id=tenant_b_id,
                    email="user-b@example.com",
                    valid_until=valid_until,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                Membership(
                    tenant_id=tenant_a_id,
                    user_id=actor_id,
                    role=Role.owner.value,
                    valid_until=valid_until,
                ),
                Membership(
                    id=tenant_b_membership_id,
                    tenant_id=tenant_b_id,
                    user_id=tenant_b_user_id,
                    role=Role.support.value,
                    valid_until=valid_until,
                ),
            ]
        )
        await session.commit()

    return tenant_a_id, actor_id, tenant_b_id, tenant_b_membership_id


@pytest.fixture
async def api_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


def _principal_override(
    tenant_id: UUID,
    user_id: UUID,
    role: Role,
) -> TenantPrincipal:
    return TenantPrincipal(user_id=user_id, tenant_id=tenant_id, role=role)


@pytest.mark.asyncio
async def test_owner_can_create_member_for_own_tenant(
    seeded_members: tuple[UUID, UUID, UUID, UUID],
    api_session: AsyncSession,
) -> None:
    tenant_id, actor_id, _, _ = seeded_members
    app.dependency_overrides[get_session] = lambda: api_session
    app.dependency_overrides[get_principal] = lambda: _principal_override(
        tenant_id, actor_id, Role.owner
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/members",
                json={"email": "new-member@example.com", "role": "operator"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["tenant_id"] == str(tenant_id)
    assert response.json()["role"] == "operator"

    count = await api_session.scalar(
        text(
            "SELECT count(*) FROM memberships "
            "WHERE tenant_id = :tenant_id AND role = :role"
        ),
        {"tenant_id": tenant_id, "role": Role.operator.value},
    )
    assert count == 1


@pytest.mark.asyncio
async def test_operator_cannot_create_member(
    seeded_members: tuple[UUID, UUID, UUID, UUID],
    api_session: AsyncSession,
) -> None:
    tenant_id, actor_id, _, _ = seeded_members
    app.dependency_overrides[get_session] = lambda: api_session
    app.dependency_overrides[get_principal] = lambda: _principal_override(
        tenant_id, actor_id, Role.operator
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/members",
                json={"email": "blocked@example.com", "role": "support"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_member_is_hidden(
    seeded_members: tuple[UUID, UUID, UUID, UUID],
    api_session: AsyncSession,
) -> None:
    tenant_id, actor_id, _, tenant_b_membership_id = seeded_members
    app.dependency_overrides[get_session] = lambda: api_session
    app.dependency_overrides[get_principal] = lambda: _principal_override(
        tenant_id, actor_id, Role.owner
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/members/{tenant_b_membership_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
