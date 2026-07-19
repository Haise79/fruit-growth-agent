from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

from fruit_agent.db import SessionFactory, engine, tenant_session
from fruit_agent.identity.models import Tenant
from fruit_agent.knowledge.models import (
    EMBEDDING_DIMENSION,
    KnowledgeType,
    MerchantKnowledge,
    ReviewStatus,
)
from fruit_agent.model_gateway.schemas import (
    AgentSuggestion,
    ModelProfile,
    ProviderResponse,
)
from fruit_agent.model_gateway.service import (
    InvalidModelOutputError,
    ModelGateway,
    ProviderBinding,
)


@pytest.fixture
async def model_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


def _provider_binding(provider: AsyncMock) -> ProviderBinding:
    return ProviderBinding(
        profile=ModelProfile(
            name="qwen-test",
            estimated_cost_per_1k_tokens=0.001,
            fact_error_rate=0.01,
            high_risk_recall=0.98,
        ),
        provider=provider,
    )


@pytest.mark.asyncio
async def test_gateway_validates_tenant_references_and_never_logs_raw_phone(
    model_database: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del model_database
    tenant_a = uuid4()
    tenant_b = uuid4()
    knowledge_b_id = uuid4()
    future = datetime.now(UTC) + timedelta(hours=1)
    embedding = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)
    async with SessionFactory() as seed:
        seed.add_all(
            [
                Tenant(id=tenant_a, name="Tenant A", valid_until=future),
                Tenant(id=tenant_b, name="Tenant B", valid_until=future),
            ]
        )
        await seed.flush()
        seed.add(
            MerchantKnowledge(
                id=knowledge_b_id,
                tenant_id=tenant_b,
                knowledge_type=KnowledgeType.faq.value,
                review_status=ReviewStatus.approved.value,
                content="跨租户知识",
                source_id=uuid4(),
                embedding=embedding,
                valid_until=future,
            )
        )
        await seed.commit()

    provider = AsyncMock()
    provider.complete.return_value = ProviderResponse(
        suggestion=AgentSuggestion(
            suggestion_text="不可信引用",
            referenced_knowledge_ids=[knowledge_b_id],
            confidence_score=0.8,
            risk_level="low",
        ),
        input_tokens=10,
        output_tokens=10,
    )
    async with SessionFactory() as session:
        async with tenant_session(session, tenant_a):
            with pytest.raises(InvalidModelOutputError):
                await ModelGateway(
                    session=session,
                    providers=[_provider_binding(provider)],
                ).suggest(
                    tenant_id=tenant_a,
                    prompt={
                        "message": "推荐苹果",
                        "phone": "13800138000",
                    },
                )

    captured = capsys.readouterr()
    assert "13800138000" not in captured.out
    assert provider.complete.await_args.args[0]["phone"] == "[REDACTED]"
