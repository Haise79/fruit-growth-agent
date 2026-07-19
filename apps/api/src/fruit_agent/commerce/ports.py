from typing import Protocol
from uuid import UUID

from fruit_agent.approvals.models import ApprovalRequest
from fruit_agent.knowledge.schemas import ProductSKURead


class CommerceAdapter(Protocol):
    async def get_product(
        self,
        *,
        tenant_id: UUID,
        sku_code: str,
    ) -> ProductSKURead | None: ...

    async def change_inventory(
        self,
        *,
        tenant_id: UUID,
        sku_code: str,
        quantity: int,
    ) -> ApprovalRequest: ...
