import csv
import io
from uuid import UUID, uuid4

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.imports.schemas import (
    ImportResult,
    ProductImportRow,
    RowError,
)
from fruit_agent.knowledge.models import ProductSKU

logger = structlog.get_logger(__name__)
REQUIRED_HEADERS = (
    "sku_code",
    "name",
    "price",
    "inventory",
    "valid_until",
)

SUGGESTIONS = {
    "sku_code": "填写唯一且非空的 SKU 编码",
    "name": "填写商品名称",
    "price": "填写大于 0 且最多两位小数的价格",
    "inventory": "填写大于或等于 0 的整数库存",
    "valid_until": "填写未来的 ISO 8601 时区日期",
}


class ImportFormatError(ValueError):
    pass


def _row_errors(
    row_number: int,
    error: ValidationError,
) -> list[RowError]:
    errors: list[RowError] = []
    for detail in error.errors():
        location = detail.get("loc", ())
        field = str(location[0]) if location else "row"
        errors.append(
            RowError(
                row_number=row_number,
                field=field,
                reason=str(detail.get("msg", "invalid value")),
                suggestion=SUGGESTIONS.get(field, "检查该字段格式"),
            )
        )
    return errors


class ManualImportAdapter:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def import_products(
        self,
        *,
        tenant_id: UUID,
        content: bytes,
    ) -> ImportResult:
        try:
            text_content = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ImportFormatError("CSV must use UTF-8 encoding") from exc

        reader = csv.DictReader(io.StringIO(text_content))
        if tuple(reader.fieldnames or ()) != REQUIRED_HEADERS:
            raise ImportFormatError(
                "CSV headers must exactly match the product template"
            )

        valid_rows: list[ProductImportRow] = []
        errors: list[RowError] = []
        seen_skus: set[str] = set()
        total_rows = 0
        source_id = uuid4()

        for row_number, raw in enumerate(reader, start=2):
            total_rows += 1
            try:
                row = ProductImportRow.model_validate(raw)
            except ValidationError as exc:
                errors.extend(_row_errors(row_number, exc))
                continue
            if row.sku_code in seen_skus:
                errors.append(
                    RowError(
                        row_number=row_number,
                        field="sku_code",
                        reason="duplicate SKU in import file",
                        suggestion="每个 CSV 文件中每个 SKU 只保留一行",
                    )
                )
                continue
            seen_skus.add(row.sku_code)
            valid_rows.append(row)

        for row in valid_rows:
            self.session.add(
                ProductSKU(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    audit_log=[{"event": "csv_import"}],
                    **row.model_dump(),
                )
            )
        if valid_rows:
            await self.session.flush()

        failed_row_numbers = {error.row_number for error in errors}
        result = ImportResult(
            total_rows=total_rows,
            imported_rows=len(valid_rows),
            failed_rows=len(failed_row_numbers),
            errors=errors,
        )
        await logger.ainfo(
            "manual_product_import_completed",
            tenant_id=str(tenant_id),
            total_rows=result.total_rows,
            imported_rows=result.imported_rows,
            failed_rows=result.failed_rows,
        )
        return result
