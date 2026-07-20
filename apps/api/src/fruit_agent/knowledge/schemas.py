from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductSKURead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    sku_code: str
    name: str
    price: Decimal
    inventory: int
    source_id: UUID


class ExactFactResult(BaseModel):
    status: Literal["ok", "expired", "conflict", "not_found"]
    sku: ProductSKURead | None = None
    conflict_source_ids: list[UUID] = Field(default_factory=list)
    requires_human: bool = False
