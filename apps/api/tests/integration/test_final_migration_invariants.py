from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fruit_agent.copilot.models import (
    CopilotCase,
    CopilotCitationSnapshot,
    CopilotSuggestion,
)
from fruit_agent.db import SessionFactory, engine
from fruit_agent.identity.models import Tenant, User
from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider
from fruit_agent.knowledge.models import MerchantKnowledge


@pytest.fixture
async def invariant_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


async def _seed_tenants_and_users() -> tuple[object, object, object, object]:
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()
    future = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as session:
        session.add_all(
            [
                Tenant(id=tenant_a_id, name="Tenant A", valid_until=future),
                Tenant(id=tenant_b_id, name="Tenant B", valid_until=future),
                User(
                    id=user_a_id,
                    tenant_id=tenant_a_id,
                    email="a@example.com",
                    valid_until=future,
                ),
                User(
                    id=user_b_id,
                    tenant_id=tenant_b_id,
                    email="b@example.com",
                    valid_until=future,
                ),
            ]
        )
        await session.commit()
    return tenant_a_id, tenant_b_id, user_a_id, user_b_id


@pytest.mark.asyncio
async def test_database_rejects_cross_tenant_responsible_user(
    invariant_database: None,
) -> None:
    del invariant_database
    tenant_a_id, _, _, user_b_id = await _seed_tenants_and_users()
    provider = DeterministicEmbeddingProvider()
    async with SessionFactory() as session:
        session.add(
            MerchantKnowledge(
                tenant_id=tenant_a_id,
                knowledge_type="faq",
                review_status="draft",
                content="Store apples cold.",
                source_id=uuid4(),
                source_name="Handbook",
                responsible_user_id=user_b_id,
                embedding=provider.embed("Store apples cold."),
                embedding_model=provider.model_name,
                embedding_version=provider.model_version,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("stage", "invalid-stage"),
        ("intent", "invalid-intent"),
        ("risk", "invalid-risk"),
        ("status", "invalid-status"),
    ],
)
async def test_database_rejects_invalid_case_enum_strings(
    invariant_database: None,
    field: str,
    invalid_value: str,
) -> None:
    del invariant_database
    tenant_id, _, user_id, _ = await _seed_tenants_and_users()
    values = {
        "stage": "presale",
        "intent": "recommendation",
        "risk": "low",
        "status": "handoff_required",
    }
    values[field] = invalid_value
    async with SessionFactory() as session:
        session.add(
            CopilotCase(
                tenant_id=tenant_id,
                created_by_user_id=user_id,
                message="redacted",
                selected_sku_codes=[],
                risk_reasons=[],
                **values,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_database_rejects_invalid_citation_type(
    invariant_database: None,
) -> None:
    del invariant_database
    tenant_id, _, user_id, _ = await _seed_tenants_and_users()
    async with SessionFactory() as session:
        case = CopilotCase(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            message="redacted",
            selected_sku_codes=[],
            stage="presale",
            intent="recommendation",
            risk="low",
            status="suggestions_ready",
            risk_reasons=[],
        )
        session.add(case)
        await session.flush()
        suggestion = CopilotSuggestion(
            tenant_id=tenant_id,
            case_id=case.id,
            original_text="Use this SKU.",
            rank=1,
            recommended_sku_code="APPLE-001",
            confidence=0.9,
            degraded=False,
        )
        session.add(suggestion)
        await session.flush()
        session.add(
            CopilotCitationSnapshot(
                tenant_id=tenant_id,
                suggestion_id=suggestion.id,
                citation_type="invalid-citation",
                source_id=uuid4(),
                source_name="invalid",
                snapshot={},
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_migration_0008_downgrade_removes_and_upgrade_restores_invariants(
    invariant_database: None,
) -> None:
    del invariant_database
    config = Config("alembic.ini")
    command.downgrade(config, "0007_copilot_outcome_events")
    async with SessionFactory() as session:
        columns = set(
            await session.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'merchant_knowledge'"
                )
            )
        )
        constraints = set(
            await session.scalars(
                text(
                    "SELECT conname FROM pg_constraint WHERE conname IN ("
                    "'fk_merchant_knowledge_tenant_responsible',"
                    "'ck_copilot_cases_stage','ck_copilot_cases_intent',"
                    "'ck_copilot_cases_risk','ck_copilot_cases_status',"
                    "'ck_copilot_citations_type')"
                )
            )
        )
        index_exists = await session.scalar(
            text(
                "SELECT to_regclass("
                "'public.ix_merchant_knowledge_tenant_responsible_user'"
                ")"
            )
        )
    assert "embedding_model" not in columns
    assert "embedding_version" not in columns
    assert constraints == set()
    assert index_exists is None

    command.upgrade(config, "head")
    async with SessionFactory() as session:
        restored = set(
            await session.scalars(
                text(
                    "SELECT conname FROM pg_constraint WHERE conname IN ("
                    "'fk_merchant_knowledge_tenant_responsible',"
                    "'ck_copilot_cases_stage','ck_copilot_cases_intent',"
                    "'ck_copilot_cases_risk','ck_copilot_cases_status',"
                    "'ck_copilot_citations_type')"
                )
            )
        )
        restored_index = await session.scalar(
            text(
                "SELECT to_regclass("
                "'public.ix_merchant_knowledge_tenant_responsible_user'"
                ")"
            )
        )
    assert restored == {
        "fk_merchant_knowledge_tenant_responsible",
        "ck_copilot_cases_stage",
        "ck_copilot_cases_intent",
        "ck_copilot_cases_risk",
        "ck_copilot_cases_status",
        "ck_copilot_citations_type",
    }
    assert restored_index == "ix_merchant_knowledge_tenant_responsible_user"
