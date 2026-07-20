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
from fruit_agent.identity.models import Membership, MembershipStatus

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

    async def list_items(self, tenant_id: UUID) -> list[MerchantKnowledge]:
        rows = await self.session.scalars(
            select(MerchantKnowledge)
            .where(MerchantKnowledge.tenant_id == tenant_id)
            .order_by(MerchantKnowledge.created_at.desc())
        )
        return list(rows)

    async def get_item(
        self,
        tenant_id: UUID,
        knowledge_id: UUID,
    ) -> MerchantKnowledge | None:
        rows = await self.session.scalars(
            select(MerchantKnowledge).where(
                MerchantKnowledge.tenant_id == tenant_id,
                MerchantKnowledge.id == knowledge_id,
            )
        )
        return rows.one_or_none()

    async def has_active_member(self, tenant_id: UUID, user_id: UUID) -> bool:
        membership = await self.session.scalar(
            select(Membership.id).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
                Membership.status == MembershipStatus.active.value,
            )
        )
        return membership is not None

    async def search_semantic(
        self,
        *,
        tenant_id: UUID,
        query_embedding: list[float],
        knowledge_types: list[KnowledgeType],
        now: datetime,
        limit: int,
        embedding_model: str | None = None,
        embedding_version: str | None = None,
    ) -> list[MerchantKnowledge]:
        allowed_types = SEMANTIC_TYPES & set(knowledge_types)
        if not allowed_types:
            return []
        conditions = [
            MerchantKnowledge.tenant_id == tenant_id,
            MerchantKnowledge.knowledge_type.in_(
                knowledge_type.value for knowledge_type in allowed_types
            ),
            MerchantKnowledge.review_status == ReviewStatus.approved.value,
            MerchantKnowledge.valid_until.is_not(None),
            MerchantKnowledge.valid_until > now,
        ]
        if embedding_model is not None:
            conditions.append(MerchantKnowledge.embedding_model == embedding_model)
        if embedding_version is not None:
            conditions.append(
                MerchantKnowledge.embedding_version == embedding_version
            )
        rows = await self.session.scalars(
            select(MerchantKnowledge)
            .where(*conditions)
            .order_by(
                MerchantKnowledge.embedding.cosine_distance(query_embedding)
            )
            .limit(limit)
        )
        return list(rows)
