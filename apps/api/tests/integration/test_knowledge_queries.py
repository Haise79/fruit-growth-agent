from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fruit_agent.db import SessionFactory, engine, tenant_session
from fruit_agent.identity.models import Tenant
from fruit_agent.knowledge.models import (
    KnowledgeType,
    MerchantKnowledge,
    ProductSKU,
    ReviewStatus,
)
from fruit_agent.knowledge.repository import KnowledgeRepository

EMBEDDING_DIMENSION = 1536


@pytest.fixture
async def knowledge_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.mark.asyncio
async def test_exact_sku_query_and_semantic_type_allowlist(
    knowledge_database: None,
) -> None:
    del knowledge_database
    tenant_a = uuid4()
    tenant_b = uuid4()
    now = datetime.now(UTC)
    future = now + timedelta(hours=1)
    embedding = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)

    async with SessionFactory() as seed:
        seed.add_all(
            [
                Tenant(id=tenant_a, name="Tenant A", valid_until=future),
                Tenant(id=tenant_b, name="Tenant B", valid_until=future),
            ]
        )
        await seed.flush()
        seed.add_all(
            [
                ProductSKU(
                    tenant_id=tenant_a,
                    sku_code="APPLE-001",
                    name="A 苹果",
                    price=Decimal("19.90"),
                    inventory=10,
                    source_id=uuid4(),
                    valid_until=future,
                ),
                ProductSKU(
                    tenant_id=tenant_b,
                    sku_code="APPLE-001",
                    name="B 苹果",
                    price=Decimal("29.90"),
                    inventory=20,
                    source_id=uuid4(),
                    valid_until=future,
                ),
                MerchantKnowledge(
                    tenant_id=tenant_a,
                    knowledge_type=KnowledgeType.faq.value,
                    review_status=ReviewStatus.approved.value,
                    content="苹果如何保存",
                    source_id=uuid4(),
                    embedding=embedding,
                    valid_until=future,
                ),
                MerchantKnowledge(
                    tenant_id=tenant_a,
                    knowledge_type=KnowledgeType.product_fact.value,
                    review_status=ReviewStatus.approved.value,
                    content="商品价格事实不可语义检索",
                    source_id=uuid4(),
                    embedding=embedding,
                    valid_until=future,
                ),
            ]
        )
        await seed.commit()

    async with SessionFactory() as session:
        async with tenant_session(session, tenant_a):
            repository = KnowledgeRepository(session)
            sku_rows = await repository.get_sku_exact(tenant_a, "APPLE-001")
            semantic_rows = await repository.search_semantic(
                tenant_id=tenant_a,
                query_embedding=embedding,
                knowledge_types=[
                    KnowledgeType.faq,
                    KnowledgeType.product_fact,
                ],
                now=now,
                limit=5,
            )

    assert len(sku_rows) == 1
    assert sku_rows[0].name == "A 苹果"
    assert [row.knowledge_type for row in semantic_rows] == [
        KnowledgeType.faq.value
    ]
