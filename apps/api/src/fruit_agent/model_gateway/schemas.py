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
