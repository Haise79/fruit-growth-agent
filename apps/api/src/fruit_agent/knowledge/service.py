from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from fruit_agent.knowledge.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
)
from fruit_agent.knowledge.models import MerchantKnowledge, ReviewStatus
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.schemas import (
    ExactFactResult,
    KnowledgeItemCreate,
    KnowledgeItemUpdate,
    ProductSKURead,
)

logger = structlog.get_logger(__name__)


class KnowledgeService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()

    async def list_items(self, tenant_id: UUID) -> list[MerchantKnowledge]:
        return await self.repository.list_items(tenant_id)

    async def create_item(
        self,
        *,
        tenant_id: UUID,
        item: KnowledgeItemCreate,
    ) -> MerchantKnowledge:
        record = MerchantKnowledge(
            tenant_id=tenant_id,
            knowledge_type=item.knowledge_type.value,
            review_status=ReviewStatus.draft.value,
            content=item.content,
            source_id=uuid4(),
            source_name=item.source_name,
            responsible_user_id=item.responsible_user_id,
            embedding=self.embedding_provider.embed(item.content),
            valid_until=item.valid_until,
        )
        self.repository.session.add(record)
        await self.repository.session.flush()
        return record

    async def update_item(
        self,
        *,
        tenant_id: UUID,
        knowledge_id: UUID,
        changes: KnowledgeItemUpdate,
    ) -> MerchantKnowledge | None:
        record = await self.repository.get_item(tenant_id, knowledge_id)
        if record is None:
            return None
        values = changes.model_dump(exclude_unset=True)
        content = values.pop("content", None)
        if content is not None:
            record.content = content
            record.embedding = self.embedding_provider.embed(content)
            record.review_status = ReviewStatus.draft.value
        knowledge_type = values.pop("knowledge_type", None)
        if knowledge_type is not None:
            record.knowledge_type = knowledge_type.value
        for field, value in values.items():
            setattr(record, field, value)
        await self.repository.session.flush()
        await self.repository.session.refresh(record)
        return record

    async def review_item(
        self,
        *,
        tenant_id: UUID,
        knowledge_id: UUID,
        review_status: ReviewStatus,
    ) -> MerchantKnowledge | None:
        record = await self.repository.get_item(tenant_id, knowledge_id)
        if record is None:
            return None
        record.review_status = review_status.value
        await self.repository.session.flush()
        await self.repository.session.refresh(record)
        return record

    async def get_recommendable_sku(
        self,
        *,
        tenant_id: UUID,
        sku_code: str,
        now: datetime | None = None,
    ) -> ExactFactResult:
        checked_at = now or datetime.now(UTC)
        rows = await self.repository.get_sku_exact(tenant_id, sku_code)
        if not rows:
            return ExactFactResult(status="not_found")

        if any(
            row.valid_until is None or row.valid_until <= checked_at
            for row in rows
        ):
            await logger.awarning(
                "sku_fact_expired",
                tenant_id=str(tenant_id),
                sku_code=sku_code,
            )
            return ExactFactResult(status="expired")

        distinct_facts = {
            (row.price, row.inventory, row.name)
            for row in rows
        }
        if len(distinct_facts) > 1:
            source_ids = [row.source_id for row in rows]
            await logger.awarning(
                "sku_fact_conflict",
                tenant_id=str(tenant_id),
                sku_code=sku_code,
                conflict_source_ids=[str(source_id) for source_id in source_ids],
            )
            return ExactFactResult(
                status="conflict",
                conflict_source_ids=source_ids,
                requires_human=True,
            )

        return ExactFactResult(
            status="ok",
            sku=ProductSKURead.model_validate(rows[0]),
        )
