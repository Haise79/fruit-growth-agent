from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CopilotStage(StrEnum):
    presale = "presale"
    aftersale = "aftersale"
    unknown = "unknown"


class CopilotIntent(StrEnum):
    product_info = "product_info"
    recommendation = "recommendation"
    gift = "gift"
    delivery = "delivery"
    storage = "storage"
    damage = "damage"
    refund = "refund"
    complaint = "complaint"
    health_safety = "health_safety"
    other = "other"


class CopilotRisk(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CopilotCaseStatus(StrEnum):
    suggestions_ready = "suggestions_ready"
    handoff_required = "handoff_required"
    degraded = "degraded"
    closed = "closed"


class CopilotCitationType(StrEnum):
    sku = "sku"
    knowledge = "knowledge"


class SafetyClassification(BaseModel):
    stage: CopilotStage
    intent: CopilotIntent
    risk: CopilotRisk
    requires_handoff: bool
    reasons: list[str]


class CopilotCaseCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    selected_sku_codes: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message may not be blank")
        return value

    @field_validator("selected_sku_codes")
    @classmethod
    def normalize_sku_codes(cls, value: list[str]) -> list[str]:
        normalized = [code.strip() for code in value]
        if any(not code for code in normalized):
            raise ValueError("selected SKU codes may not be blank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("selected SKU codes must be unique")
        return normalized


class CopilotSuggestionEdit(BaseModel):
    edited_text: str = Field(min_length=1, max_length=4000)

    @field_validator("edited_text")
    @classmethod
    def edited_text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("edited_text may not be blank")
        return value


class CopilotCitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    citation_type: CopilotCitationType
    source_id: UUID
    source_name: str
    snapshot: dict[str, Any]
    created_at: datetime


class CopilotSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_text: str
    edited_text: str | None
    rank: int
    recommended_sku_code: str | None
    confidence: float
    risk_tip: str | None
    degraded: bool
    citations: list[CopilotCitationRead]
    created_at: datetime
    updated_at: datetime


class CopilotCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_by_user_id: UUID
    message: str
    selected_sku_codes: list[str]
    stage: CopilotStage
    intent: CopilotIntent
    risk: CopilotRisk
    status: CopilotCaseStatus
    risk_reasons: list[str]
    suggestions: list[CopilotSuggestionRead]
    created_at: datetime
    updated_at: datetime
