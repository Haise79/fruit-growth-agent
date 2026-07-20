from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.approvals.models import ApprovalRequest, ApprovalStatus
from fruit_agent.db import SessionFactory, engine, get_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal


@pytest.fixture
async def approval_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
async def approval_context(
    approval_database: None,
) -> tuple[TenantPrincipal, TenantPrincipal, AsyncSession]:
    del approval_database
    tenant_id = uuid4()
    operator_id = uuid4()
    owner_id = uuid4()
    valid_until = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as seed_session:
        seed_session.add(
            Tenant(id=tenant_id, name="Approval Tenant", valid_until=valid_until)
        )
        await seed_session.flush()
        seed_session.add_all(
            [
                User(
                    id=operator_id,
                    tenant_id=tenant_id,
                    email="operator@example.com",
                    valid_until=valid_until,
                ),
                User(
                    id=owner_id,
                    tenant_id=tenant_id,
                    email="owner@example.com",
                    valid_until=valid_until,
                ),
            ]
        )
        await seed_session.commit()

    return (
        TenantPrincipal(
            tenant_id=tenant_id,
            user_id=operator_id,
            role=Role.operator,
        ),
        TenantPrincipal(
            tenant_id=tenant_id,
            user_id=owner_id,
            role=Role.owner,
        ),
        SessionFactory(),
    )


@pytest.mark.asyncio
async def test_request_and_decision_never_execute_risky_payload(
    approval_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    operator, owner, session = approval_context
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = await client.post(
                "/api/v1/approvals",
                json={
                    "action": "change_inventory",
                    "payload": {
                        "sku": "APPLE-001",
                        "quantity": 0,
                        "receiver_phone": "13800138000",
                    },
                },
            )
            assert created.status_code == 201
            body = created.json()
            assert body["requires_approval"] is True
            assert body["status"] == "pending"
            assert body["payload"]["receiver_phone"] == "[REDACTED]"

            app.dependency_overrides[get_principal] = lambda: owner
            decided = await client.post(
                f"/api/v1/approvals/{body['id']}/decision",
                json={"decision": "approved"},
            )
    finally:
        app.dependency_overrides.clear()

    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert decided.json()["requires_approval"] is True

    stored = await session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == operator.tenant_id,
            ApprovalRequest.id == body["id"],
        )
    )
    assert stored is not None
    assert stored.status == ApprovalStatus.approved.value
    assert stored.payload["quantity"] == 0
    await session.close()
