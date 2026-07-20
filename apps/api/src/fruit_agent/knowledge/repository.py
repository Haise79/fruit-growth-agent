from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.knowledge.models import (
    KnowledgeType,
    MerchantKnowledge,
    ProductSKU,
    ReviewStatus,
)

SEMANTIC_TYPES = {
    KnowledgeType.faq,
    KnowledgeType.talking_point,
    KnowledgeType.origin_story,
}


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_sku_exact(
        self,
        tenant_id: UUID,
        sku_code: str,
    ) -> list[ProductSKU]:
        rows = await self.session.scalars(
            select(ProductSKU).where(
                ProductSKU.tenant_id == tenant_id,
                ProductSKU.sku_code == sku_code,
            )
        )
        return list(rows)

    async def search_semantic(
        self,
        *,
        tenant_id: UUID,
        query_embedding: list[float],
        knowledge_types: list[KnowledgeType],
        now: datetime,
        limit: int,
    ) -> list[MerchantKnowledge]:
        allowed_types = SEMANTIC_TYPES & set(knowledge_types)
        if not allowed_types:
            return []
        rows = await self.session.scalars(
            select(MerchantKnowledge)
            .where(
                MerchantKnowledge.tenant_id == tenant_id,
                MerchantKnowledge.knowledge_type.in_(
                    knowledge_type.value for knowledge_type in allowed_types
                ),
                MerchantKnowledge.review_status == ReviewStatus.approved.value,
                MerchantKnowledge.valid_until.is_not(None),
                MerchantKnowledge.valid_until > now,
            )
            .order_by(
                MerchantKnowledge.embedding.cosine_distance(query_embedding)
            )
            .limit(limit)
        )
        return list(rows)
