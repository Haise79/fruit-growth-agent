import asyncio
from decimal import Decimal
from time import perf_counter
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fruit_agent.model_gateway.schemas import (
    CopilotAgentOutput,
    CopilotAgentSuggestion,
    CopilotProviderResponse,
    CopilotSKUFactClaims,
    ModelProfile,
)
from fruit_agent.model_gateway.service import ModelGateway, ProviderBinding
from fruit_agent.model_gateway.service import ProviderUnavailableError


def test_copilot_suggestion_requires_complete_structured_fact_claims() -> None:
    with pytest.raises(ValidationError):
        CopilotAgentSuggestion.model_validate(
            {
                "suggestion_text": "Model free text",
                "recommended_sku_code": "APPLE-001",
                "confidence_score": 0.9,
            }
        )

    with pytest.raises(ValidationError):
        CopilotAgentSuggestion.model_validate(
            {
                "suggestion_text": "Model free text",
                "recommended_sku_code": "APPLE-001",
                "confidence_score": 0.9,
                "fact_claims": {"price": "29.90"},
            }
        )

    with pytest.raises(ValidationError):
        CopilotAgentSuggestion.model_validate(
            {
                "suggestion_text": "Model free text",
                "recommended_sku_code": "APPLE-001",
                "confidence_score": 0.9,
                "fact_claims": {
                    "price": "29.90",
                    "currency": "CNY",
                    "inventory": 100,
                    "origin": "山东烟台",
                    "net_weight_grams": 2500,
                },
            }
        )


@pytest.mark.asyncio
async def test_typed_copilot_output_uses_quality_gated_provider_and_redacts_message() -> None:
    provider = AsyncMock()
    provider.complete.return_value = CopilotProviderResponse(
        output=CopilotAgentOutput(
            stage="presale",
            intent="recommendation",
            risk_level="medium",
            suggestions=[
                CopilotAgentSuggestion(
                    suggestion_text="推荐新鲜红富士。",
                    referenced_knowledge_ids=[],
                    recommended_sku_code="APPLE-001",
                    confidence_score=0.91,
                    risk_tip="确认收货地区。",
                    fact_claims=CopilotSKUFactClaims(
                        price=Decimal("29.90"),
                        currency="CNY",
                        inventory=100,
                        origin="山东烟台",
                        net_weight_grams=2500,
                        shipping_eta=None,
                    ),
                )
            ],
        ),
        input_tokens=20,
        output_tokens=12,
    )
    gateway = ModelGateway(
        session=AsyncMock(),
        providers=[
            ProviderBinding(
                profile=ModelProfile(
                    name="qualified-copilot",
                    estimated_cost_per_1k_tokens=0.001,
                    fact_error_rate=0.01,
                    high_risk_recall=0.98,
                ),
                provider=provider,
            )
        ],
    )

    result = await gateway.suggest_copilot(
        tenant_id=uuid4(),
        prompt={"message": "请联系 13800138000 推荐苹果"},
    )

    assert result.stage == "presale"
    assert result.intent == "recommendation"
    assert len(result.suggestions) == 1
    assert result.suggestions[0].recommended_sku_code == "APPLE-001"
    sent_prompt = provider.complete.await_args.args[0]
    assert "13800138000" not in repr(sent_prompt)
    assert "[REDACTED]" in repr(sent_prompt)


@pytest.mark.asyncio
async def test_copilot_retry_and_failover_share_one_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fruit_agent.model_gateway.service as gateway_service

    async def slow_provider(
        prompt: dict[str, object],
        timeout_seconds: float,
    ) -> CopilotProviderResponse:
        del prompt, timeout_seconds
        await asyncio.sleep(1)
        raise ProviderUnavailableError("offline")

    primary = AsyncMock()
    fallback = AsyncMock()
    primary.complete.side_effect = slow_provider
    fallback.complete.side_effect = slow_provider
    monkeypatch.setattr(gateway_service, "MODEL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(
        gateway_service,
        "COPILOT_TOTAL_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )
    gateway = ModelGateway(
        session=AsyncMock(),
        providers=[
            _provider_binding("primary", primary, 0.001),
            _provider_binding("fallback", fallback, 0.002),
        ],
    )

    started = perf_counter()
    with pytest.raises(ProviderUnavailableError):
        await gateway.suggest_copilot(
            tenant_id=uuid4(),
            prompt={"message": "recommend apples"},
        )
    elapsed = perf_counter() - started

    assert elapsed < 0.08


def _provider_binding(
    name: str,
    provider: AsyncMock,
    cost: float,
) -> ProviderBinding:
    return ProviderBinding(
        profile=ModelProfile(
            name=name,
            estimated_cost_per_1k_tokens=cost,
            fact_error_rate=0.01,
            high_risk_recall=0.98,
        ),
        provider=provider,
    )
