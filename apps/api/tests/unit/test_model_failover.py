from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from fruit_agent.model_gateway.schemas import (
    AgentSuggestion,
    ModelProfile,
    ProviderResponse,
)
from fruit_agent.model_gateway.service import ModelGateway, ProviderBinding


@pytest.mark.asyncio
async def test_retries_twice_then_falls_back_and_redacts_prompt() -> None:
    tenant_id = uuid4()
    primary = AsyncMock()
    fallback = AsyncMock()
    primary.complete.side_effect = TimeoutError
    fallback.complete.return_value = ProviderResponse(
        suggestion=AgentSuggestion(
            suggestion_text="推荐当季苹果",
            referenced_knowledge_ids=[],
            confidence_score=0.9,
            risk_level="low",
        ),
        input_tokens=20,
        output_tokens=10,
    )
    session = AsyncMock()
    gateway = ModelGateway(
        session=session,
        providers=[
            ProviderBinding(
                profile=ModelProfile(
                    name="qwen-fast",
                    estimated_cost_per_1k_tokens=0.001,
                    fact_error_rate=0.01,
                    high_risk_recall=0.98,
                ),
                provider=primary,
            ),
            ProviderBinding(
                profile=ModelProfile(
                    name="glm-backup",
                    estimated_cost_per_1k_tokens=0.002,
                    fact_error_rate=0.01,
                    high_risk_recall=0.99,
                ),
                provider=fallback,
            ),
        ],
    )

    result = await gateway.suggest(
        tenant_id=tenant_id,
        prompt={"message": "推荐苹果", "phone": "13800138000"},
    )

    assert primary.complete.await_count == 3
    assert fallback.complete.await_count == 1
    assert result.degraded is True
    fallback_prompt = fallback.complete.await_args.args[0]
    assert fallback_prompt["phone"] == "[REDACTED]"
