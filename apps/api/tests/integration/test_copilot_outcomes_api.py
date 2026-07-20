import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.audit.models import AuditEvent
from fruit_agent.audit.service import AuditService
from fruit_agent.copilot.models import CopilotCase, CopilotSuggestion
from fruit_agent.copilot.outcomes import CopilotOutcomeEvent
from fruit_agent.copilot.repository import CopilotRepository
from fruit_agent.copilot.schemas import CopilotOutcomeEventCreate, CopilotOutcomeEventType
from fruit_agent.copilot.service import CopilotService
from fruit_agent.db import SessionFactory, engine, get_session, tenant_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Membership, Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal


@pytest.fixture
async def outcomes_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
async def outcomes_context(
    outcomes_database: None,
) -> tuple[TenantPrincipal, TenantPrincipal, AsyncSession]:
    del outcomes_database
    tenant_a_id, tenant_b_id = uuid4(), uuid4()
    user_a_id, user_b_id = uuid4(), uuid4()
    future = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as seed:
        seed.add_all(
            [
                Tenant(id=tenant_a_id, name="Tenant A", valid_until=future),
                Tenant(id=tenant_b_id, name="Tenant B", valid_until=future),
                User(id=user_a_id, tenant_id=tenant_a_id, email="a@example.com", valid_until=future),
                User(id=user_b_id, tenant_id=tenant_b_id, email="b@example.com", valid_until=future),
            ]
        )
        await seed.flush()
        seed.add_all(
            [
                Membership(tenant_id=tenant_a_id, user_id=user_a_id, role=Role.support.value, valid_until=future),
                Membership(tenant_id=tenant_b_id, user_id=user_b_id, role=Role.support.value, valid_until=future),
            ]
        )
        await seed.commit()
    return (
        TenantPrincipal(tenant_id=tenant_a_id, user_id=user_a_id, role=Role.support),
        TenantPrincipal(tenant_id=tenant_b_id, user_id=user_b_id, role=Role.support),
        SessionFactory(),
    )


async def _seed_case(principal: TenantPrincipal, *, with_suggestion: bool = True) -> tuple[UUID, UUID | None]:
    async with SessionFactory() as seed:
        case = CopilotCase(
            tenant_id=principal.tenant_id,
            created_by_user_id=principal.user_id,
            message="Customer message",
            selected_sku_codes=[],
            stage="presale",
            intent="recommendation",
            risk="low",
            status="suggestions_ready",
            risk_reasons=[],
        )
        seed.add(case)
        await seed.flush()
        suggestion_id: UUID | None = None
        if with_suggestion:
            suggestion = CopilotSuggestion(
                tenant_id=principal.tenant_id,
                case_id=case.id,
                original_text="Suggested reply",
                rank=1,
                confidence=0.9,
            )
            seed.add(suggestion)
            await seed.flush()
            suggestion_id = suggestion.id
        await seed.commit()
        return case.id, suggestion_id


async def _client(
    session: AsyncSession,
    principal: TenantPrincipal,
) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: principal
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def _outcome_service(session: AsyncSession) -> CopilotService:
    from fruit_agent.knowledge.repository import KnowledgeRepository

    return CopilotService(
        repository=CopilotRepository(session),
        knowledge_repository=KnowledgeRepository(session),
        providers=[],
    )


@pytest.mark.asyncio
async def test_outcome_duplicate_returns_original_and_records_one_row(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, suggestion_id = await _seed_case(tenant_a)
    assert suggestion_id is not None

    async for client in _client(session, tenant_a):
        first = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "adopt-1"},
            json={"event_type": "suggestion_adopted", "suggestion_id": str(suggestion_id)},
        )
        duplicate = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "adopt-1"},
            json={"event_type": "suggestion_adopted", "suggestion_id": str(suggestion_id)},
        )

    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == first.json()["id"]
    async with tenant_session(session, tenant_a.tenant_id):
        count = await session.scalar(select(func.count()).select_from(CopilotOutcomeEvent))
        audits = await session.scalar(select(func.count()).select_from(AuditEvent))
    assert count == 1
    assert audits == 1
    await session.close()


@pytest.mark.asyncio
async def test_outcome_rejects_foreign_case_and_suggestion(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, tenant_b, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a)
    _, foreign_suggestion_id = await _seed_case(tenant_a)
    foreign_case_id, _ = await _seed_case(tenant_b)
    assert foreign_suggestion_id is not None

    async for client in _client(session, tenant_a):
        wrong_suggestion = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "wrong-suggestion"},
            json={"event_type": "payment", "suggestion_id": str(foreign_suggestion_id)},
        )
        hidden_case = await client.post(
            f"/api/v1/copilot/cases/{foreign_case_id}/events",
            headers={"Idempotency-Key": "foreign-case"},
            json={"event_type": "payment"},
        )

    assert wrong_suggestion.status_code == 404
    assert hidden_case.status_code == 404
    await session.close()


@pytest.mark.asyncio
async def test_close_case_rejects_later_nonduplicate_event(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a)

    async for client in _client(session, tenant_a):
        closed = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "close-case"},
            json={"event_type": "case_closed"},
        )
        late = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "late-payment"},
            json={"event_type": "payment"},
        )
        replay_close = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "close-case"},
            json={"event_type": "case_closed"},
        )

    assert closed.status_code == 201
    assert closed.json()["case_status"] == "closed"
    assert late.status_code == 409
    assert replay_close.status_code == 201
    assert replay_close.json()["id"] == closed.json()["id"]
    await session.close()


@pytest.mark.asyncio
async def test_outcome_redacts_metadata_and_audit_snapshot(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a)

    async for client in _client(session, tenant_a):
        response = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "redacted-metadata"},
            json={
                "event_type": "complaint",
                "metadata": {"phone": "13800138000", "note": "Call 13900139000"},
            },
        )

    assert response.status_code == 201
    assert "13800138000" not in repr(response.json())
    assert "13900139000" not in repr(response.json())
    async with tenant_session(session, tenant_a.tenant_id):
        audit = await session.scalar(select(AuditEvent).where(AuditEvent.entity_id == UUID(response.json()["id"])))
    assert audit is not None
    assert "13800138000" not in repr(audit.after)
    assert "13900139000" not in repr(audit.after)
    await session.close()


@pytest.mark.asyncio
async def test_outcome_requires_nonblank_bounded_idempotency_key(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a)

    async for client in _client(session, tenant_a):
        blank = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "   "},
            json={"event_type": "payment"},
        )
        oversized = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "x" * 201},
            json={"event_type": "payment"},
        )

    assert blank.status_code == 422
    assert oversized.status_code == 422
    await session.close()


@pytest.mark.asyncio
async def test_suggestion_outcomes_require_a_same_case_suggestion(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a, with_suggestion=False)

    async for client in _client(session, tenant_a):
        response = await client.post(
            f"/api/v1/copilot/cases/{case_id}/events",
            headers={"Idempotency-Key": "missing-suggestion"},
            json={"event_type": "suggestion_adopted"},
        )

    assert response.status_code == 422
    await session.close()


@pytest.mark.asyncio
async def test_outcome_database_rejects_suggestion_from_another_case(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a, with_suggestion=False)
    _, foreign_suggestion_id = await _seed_case(tenant_a)
    assert foreign_suggestion_id is not None

    async with tenant_session(session, tenant_a.tenant_id):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    text(
                        "INSERT INTO copilot_outcome_events "
                        "(id, tenant_id, case_id, suggestion_id, event_type, idempotency_key) "
                        "VALUES (:id, :tenant_id, :case_id, :suggestion_id, 'payment', 'wrong-case')"
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_a.tenant_id,
                        "case_id": case_id,
                        "suggestion_id": foreign_suggestion_id,
                    },
                )
    await session.close()


@pytest.mark.asyncio
async def test_concurrent_duplicate_and_close_late_event_are_serialized(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a, with_suggestion=False)
    barrier = asyncio.Barrier(2)

    async def record(event_type: CopilotOutcomeEventType, key: str) -> object:
        async with SessionFactory() as worker_session:
            async with tenant_session(worker_session, tenant_a.tenant_id):
                await barrier.wait()
                result = await _outcome_service(worker_session).record_outcome_event(
                    tenant_id=tenant_a.tenant_id,
                    case_id=case_id,
                    idempotency_key=key,
                    request=CopilotOutcomeEventCreate(event_type=event_type),
                )
                assert result is not None
                event, _, duplicate = result
                if not duplicate:
                    await AuditService(
                        session=worker_session,
                        principal=tenant_a,
                        request_id=f"race-{key}",
                    ).record(
                        action="copilot_outcome_recorded",
                        entity_type="copilot_outcome_event",
                        entity_id=event.id,
                        before={},
                        after={"event_type": event.event_type},
                    )
                return event.id

    first_id, second_id = await asyncio.gather(
        record(CopilotOutcomeEventType.payment, "same-key"),
        record(CopilotOutcomeEventType.payment, "same-key"),
    )

    assert first_id == second_id
    async with tenant_session(session, tenant_a.tenant_id):
        assert await session.scalar(select(func.count()).select_from(CopilotOutcomeEvent)) == 1
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1

    async with SessionFactory() as lock_session:
        async with tenant_session(lock_session, tenant_a.tenant_id):
            await lock_session.scalar(
                select(CopilotCase)
                .where(CopilotCase.tenant_id == tenant_a.tenant_id, CopilotCase.id == case_id)
                .with_for_update()
            )
            close_task = asyncio.create_task(
                record(CopilotOutcomeEventType.case_closed, "close-race")
            )
            await asyncio.sleep(0.05)
            late_task = asyncio.create_task(
                record(CopilotOutcomeEventType.payment, "late-race")
            )
            await asyncio.sleep(0.05)

    close_result, late_result = await asyncio.gather(
        close_task,
        late_task,
        return_exceptions=True,
    )
    assert isinstance(close_result, UUID)
    assert isinstance(late_result, Exception)
    assert getattr(late_result, "status_code", None) == 409
    await session.close()


@pytest.mark.asyncio
async def test_outcome_migration_round_trip_enforces_immutability_and_restores_rls(
    outcomes_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = outcomes_context
    case_id, _ = await _seed_case(tenant_a, with_suggestion=False)
    event_id = uuid4()
    async with tenant_session(session, tenant_a.tenant_id):
        session.add(
            CopilotOutcomeEvent(
                id=event_id,
                tenant_id=tenant_a.tenant_id,
                case_id=case_id,
                event_type="payment",
                idempotency_key="mutation-test",
            )
        )
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(
                    text("UPDATE copilot_outcome_events SET event_type = 'refund' WHERE id = :id"),
                    {"id": event_id},
                )
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(
                    text("DELETE FROM copilot_outcome_events WHERE id = :id"),
                    {"id": event_id},
                )
    await session.close()
    config = Config("alembic.ini")
    command.downgrade(config, "0006_copilot_cases")
    async with SessionFactory() as downgraded_session:
        missing_table = await downgraded_session.scalar(
            text("SELECT to_regclass('public.copilot_outcome_events')")
        )
    assert missing_table is None
    command.upgrade(config, "head")
    async with SessionFactory() as session:
        flags = await session.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname = 'copilot_outcome_events'"
            )
        )
    assert flags.one() == (True, True)
