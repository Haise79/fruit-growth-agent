from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.audit.models import AuditEvent
from fruit_agent.audit.service import AuditService
from fruit_agent.db import SessionFactory, engine, get_session, tenant_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal


@pytest.fixture
async def audit_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
async def audit_context(
    audit_database: None,
) -> tuple[TenantPrincipal, AsyncSession]:
    del audit_database
    tenant_id = uuid4()
    user_id = uuid4()
    valid_until = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as seed_session:
        seed_session.add(
            Tenant(id=tenant_id, name="Audit Tenant", valid_until=valid_until)
        )
        await seed_session.flush()
        seed_session.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email="auditor@example.com",
                valid_until=valid_until,
            )
        )
        await seed_session.commit()

    session = SessionFactory()
    return (
        TenantPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            role=Role.owner,
        ),
        session,
    )


@pytest.mark.asyncio
async def test_success_and_validation_error_include_request_id(
    audit_context: tuple[TenantPrincipal, AsyncSession],
) -> None:
    principal, session = audit_context
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: principal

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            success = await client.post(
                "/api/v1/members",
                json={"email": "member@example.com", "role": "support"},
            )
            validation_error = await client.post(
                "/api/v1/members",
                json={"email": "invalid-email", "role": "support"},
            )
    finally:
        app.dependency_overrides.clear()
        await session.close()

    assert success.status_code == 201
    assert success.headers["X-Request-ID"]
    assert validation_error.status_code == 422
    assert validation_error.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_audit_service_redacts_and_database_rejects_mutation(
    audit_context: tuple[TenantPrincipal, AsyncSession],
) -> None:
    principal, session = audit_context
    event_id: UUID
    try:
        async with tenant_session(session, principal.tenant_id):
            event = await AuditService(
                session=session,
                principal=principal,
                request_id="request-audit-test",
            ).record(
                action="customer.updated",
                entity_type="customer",
                entity_id=uuid4(),
                before={"phone": "13800138000"},
                after={"profile": {"address": "上海市浦东新区"}},
            )
            event_id = event.id

        async with tenant_session(session, principal.tenant_id):
            stored = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == principal.tenant_id,
                    AuditEvent.id == event_id,
                )
            )
            assert stored is not None
            assert stored.before == {"phone": "[REDACTED]"}
            assert stored.after == {"profile": {"address": "[REDACTED]"}}

        with pytest.raises(Exception, match="audit events are immutable"):
            async with tenant_session(session, principal.tenant_id):
                await session.execute(
                    text(
                        "UPDATE audit_events SET action = 'tampered' "
                        "WHERE tenant_id = :tenant_id AND id = :event_id"
                    ),
                    {"tenant_id": principal.tenant_id, "event_id": event_id},
                )
    finally:
        await session.close()
