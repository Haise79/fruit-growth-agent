from datetime import UTC, datetime
from uuid import UUID

import structlog

from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.schemas import ExactFactResult, ProductSKURead

logger = structlog.get_logger(__name__)


class KnowledgeService:
    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

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
