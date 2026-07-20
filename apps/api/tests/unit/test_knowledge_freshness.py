from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from fruit_agent.knowledge.models import ProductSKU
from fruit_agent.knowledge.service import KnowledgeService


def _sku(*, valid_until: datetime, price: str = "19.90") -> ProductSKU:
    return ProductSKU(
        tenant_id=uuid4(),
        sku_code="APPLE-001",
        name="红富士苹果",
        price=Decimal(price),
        inventory=100,
        source_id=uuid4(),
        valid_until=valid_until,
    )


@pytest.mark.asyncio
async def test_expired_price_returns_expired_without_recommendation() -> None:
    now = datetime.now(UTC)
    expired_sku = _sku(valid_until=now - timedelta(seconds=1))
    repository = AsyncMock()
    repository.get_sku_exact.return_value = [expired_sku]
    service = KnowledgeService(repository)

    result = await service.get_recommendable_sku(
        tenant_id=expired_sku.tenant_id,
        sku_code=expired_sku.sku_code,
        now=now,
    )

    assert result.status == "expired"
    assert result.sku is None


@pytest.mark.asyncio
async def test_conflicting_facts_require_human_review() -> None:
    now = datetime.now(UTC)
    first = _sku(valid_until=now + timedelta(hours=1), price="19.90")
    second = _sku(valid_until=now + timedelta(hours=1), price="29.90")
    second.tenant_id = first.tenant_id
    repository = AsyncMock()
    repository.get_sku_exact.return_value = [first, second]
    service = KnowledgeService(repository)

    result = await service.get_recommendable_sku(
        tenant_id=first.tenant_id,
        sku_code=first.sku_code,
        now=now,
    )

    assert result.status == "conflict"
    assert result.sku is None
    assert result.requires_human is True
    assert set(result.conflict_source_ids) == {first.source_id, second.source_id}
