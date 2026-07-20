from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from fruit_agent.knowledge.models import KnowledgeType, ReviewStatus


class ProductSKURead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    sku_code: str
    name: str
    price: Decimal
    inventory: int
    source_id: UUID
    variety: str | None = None
    origin: str | None = None
    orchard: str | None = None
    taste: str | None = None
    ripeness: str | None = None
    specification: str | None = None
    net_weight_grams: int | None = None
    sales_regions: list[str] | None = None
    shipping_eta: str | None = None
    valid_until: datetime | None = None


class KnowledgeItemCreate(BaseModel):
    knowledge_type: KnowledgeType
    content: str = Field(min_length=1)
    source_name: str = Field(min_length=1, max_length=300)
    responsible_user_id: UUID
    valid_until: AwareDatetime

    @field_validator("valid_until")
    @classmethod
    def valid_until_must_be_future(cls, value: datetime) -> datetime:
        if value <= datetime.now(UTC):
            raise ValueError("valid_until must be in the future")
        return value


class KnowledgeItemUpdate(BaseModel):
    knowledge_type: KnowledgeType | None = None
    content: str | None = Field(default=None, min_length=1)
    source_name: str | None = Field(default=None, min_length=1, max_length=300)
    responsible_user_id: UUID | None = None
    valid_until: AwareDatetime | None = None

    @field_validator("valid_until")
    @classmethod
    def renewed_valid_until_must_be_future(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value <= datetime.now(UTC):
            raise ValueError("valid_until must be in the future")
        return value

    @model_validator(mode="after")
    def reject_explicit_nulls_for_required_fields(self) -> "KnowledgeItemUpdate":
        for field_name in (
            "source_name",
            "responsible_user_id",
            "valid_until",
        ):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} may not be null")
        return self


class KnowledgeReviewRequest(BaseModel):
    review_status: Literal[ReviewStatus.approved, ReviewStatus.rejected]


class KnowledgeItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    knowledge_type: KnowledgeType
    review_status: ReviewStatus
    content: str
    source_id: UUID
    source_name: str
    responsible_user_id: UUID | None
    embedding_model: str
    embedding_version: str
    valid_until: datetime | None
    created_at: datetime
    updated_at: datetime


class ExactFactResult(BaseModel):
    status: Literal["ok", "expired", "conflict", "not_found"]
    sku: ProductSKURead | None = None
    conflict_source_ids: list[UUID] = Field(default_factory=list)
    requires_human: bool = False
