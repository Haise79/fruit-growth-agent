from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.imports.manual import ImportFormatError, ManualImportAdapter


@pytest.mark.asyncio
async def test_csv_import_reports_each_invalid_row() -> None:
    session = AsyncMock(spec=AsyncSession)
    adapter = ManualImportAdapter(session)
    content = (
        b"sku_code,name,price,inventory,valid_until\n"
        b"A1,\xe8\x8b\xb9\xe6\x9e\x9c,29.90,10,2030-01-01T00:00:00Z\n"
        b"A2,\xe6\xa2\xa8,-1,x,2020-01-01T00:00:00Z\n"
    )

    result = await adapter.import_products(
        tenant_id=uuid4(),
        content=content,
    )

    assert result.total_rows == 2
    assert result.imported_rows == 1
    assert result.failed_rows == 1
    assert {(error.row_number, error.field) for error in result.errors} == {
        (3, "price"),
        (3, "inventory"),
        (3, "valid_until"),
    }


@pytest.mark.asyncio
async def test_csv_import_rejects_wrong_headers_and_bad_encoding() -> None:
    adapter = ManualImportAdapter(AsyncMock(spec=AsyncSession))

    with pytest.raises(ImportFormatError, match="headers"):
        await adapter.import_products(
            tenant_id=uuid4(),
            content=b"sku,name\nA1,Apple\n",
        )
    with pytest.raises(ImportFormatError, match="UTF-8"):
        await adapter.import_products(
            tenant_id=uuid4(),
            content=b"\xff\xfe\x00",
        )


@pytest.mark.asyncio
async def test_duplicate_sku_is_reported_per_row() -> None:
    adapter = ManualImportAdapter(AsyncMock(spec=AsyncSession))
    content = (
        b"sku_code,name,price,inventory,valid_until\n"
        b"A1,Apple,29.90,10,2030-01-01T00:00:00Z\n"
        b"A1,Apple,29.90,10,2030-01-01T00:00:00Z\n"
    )

    result = await adapter.import_products(tenant_id=uuid4(), content=content)

    assert result.imported_rows == 1
    assert result.failed_rows == 1
    assert result.errors[0].row_number == 3
    assert result.errors[0].field == "sku_code"
