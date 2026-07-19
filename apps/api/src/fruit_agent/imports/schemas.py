from datetime import UTC, datetime
from decimal import Decimal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ProductImportRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sku_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    inventory: int = Field(ge=0)
    valid_until: AwareDatetime

    @field_validator("valid_until")
    @classmethod
    def require_future_validity(cls, value: datetime) -> datetime:
        if value <= datetime.now(UTC):
            raise ValueError("valid_until must be in the future")
        return value


class RowError(BaseModel):
    row_number: int
    field: str
    reason: str
    suggestion: str


class ImportResult(BaseModel):
    total_rows: int
    imported_rows: int
    failed_rows: int
    errors: list[RowError]
