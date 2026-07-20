from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AgentSuggestion(BaseModel):
    suggestion_text: str = Field(min_length=1, max_length=4000)
    referenced_knowledge_ids: list[UUID]
    confidence_score: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high", "critical"]


class ModelProfile(BaseModel):
    name: str
    estimated_cost_per_1k_tokens: float = Field(ge=0)
    fact_error_rate: float = Field(ge=0, le=1)
    high_risk_recall: float = Field(ge=0, le=1)


class ProviderResponse(BaseModel):
    suggestion: AgentSuggestion
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class GatewaySuggestion(AgentSuggestion):
    model_name: str
    degraded: bool
    retry_count: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)


class SuggestionRequest(BaseModel):
    prompt: dict[str, object]
    knowledge_ids: list[UUID] = Field(default_factory=list)


class CopilotSKUFactClaims(BaseModel):
    price: Decimal = Field(ge=0)
    currency: str = Field(min_length=1, max_length=16)
    inventory: int = Field(ge=0)
    origin: str | None = Field(max_length=300)
    net_weight_grams: int | None = Field(ge=0)
    shipping_eta: str | None = Field(min_length=1, max_length=200)


class CopilotAgentSuggestion(BaseModel):
    suggestion_text: str = Field(min_length=1, max_length=4000)
    referenced_knowledge_ids: list[UUID] = Field(default_factory=list)
    recommended_sku_code: str | None = Field(default=None, min_length=1, max_length=128)
    confidence_score: float = Field(ge=0, le=1)
    risk_tip: str | None = Field(default=None, max_length=1000)
    fact_claims: CopilotSKUFactClaims


class CopilotAgentOutput(BaseModel):
    stage: Literal["presale", "aftersale", "unknown"]
    intent: Literal[
        "product_info",
        "recommendation",
        "gift",
        "delivery",
        "storage",
        "damage",
        "refund",
        "complaint",
        "health_safety",
        "other",
    ]
    risk_level: Literal["low", "medium", "high", "critical"]
    suggestions: list[CopilotAgentSuggestion] = Field(max_length=3)


class CopilotProviderResponse(BaseModel):
    output: CopilotAgentOutput
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class CopilotGatewayOutput(CopilotAgentOutput):
    model_name: str
    degraded: bool
    retry_count: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
