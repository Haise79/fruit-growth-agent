from typing import Protocol
from uuid import UUID

from fruit_agent.approvals.models import ApprovalRequest, RiskyAction
from fruit_agent.knowledge.schemas import ProductSKURead
from fruit_agent.knowledge.service import KnowledgeService


class ApprovalRequester(Protocol):
    async def request(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        action: RiskyAction,
        payload: dict[str, object],
    ) -> ApprovalRequest: ...


class DouyinShopAdapterMock:
    """Read-only placeholder until Douyin OAuth permissions are approved."""

    def __init__(
        self,
        *,
        approvals: ApprovalRequester,
        actor_id: UUID,
        knowledge: KnowledgeService | None = None,
    ) -> None:
        self.approvals = approvals
        self.actor_id = actor_id
        self.knowledge = knowledge
        self.executed_actions: list[dict[str, object]] = []

    async def get_product(
        self,
        *,
        tenant_id: UUID,
        sku_code: str,
    ) -> ProductSKURead | None:
        if self.knowledge is None:
            return None
        result = await self.knowledge.get_recommendable_sku(
            tenant_id=tenant_id,
            sku_code=sku_code,
        )
        return result.sku if result.status == "ok" else None

    async def _request_only(
        self,
        *,
        tenant_id: UUID,
        action: RiskyAction,
        payload: dict[str, object],
    ) -> ApprovalRequest:
        return await self.approvals.request(
            tenant_id=tenant_id,
            actor_id=self.actor_id,
            action=action,
            payload=payload,
        )

    async def refund(
        self,
        *,
        tenant_id: UUID,
        order_id: str,
        amount: int | float,
    ) -> ApprovalRequest:
        return await self._request_only(
            tenant_id=tenant_id,
            action=RiskyAction.refund,
            payload={"order_id": order_id, "amount": amount},
        )

    async def compensate(
        self,
        *,
        tenant_id: UUID,
        order_id: str,
        amount: int | float,
    ) -> ApprovalRequest:
        return await self._request_only(
            tenant_id=tenant_id,
            action=RiskyAction.compensate,
            payload={"order_id": order_id, "amount": amount},
        )

    async def change_price(
        self,
        *,
        tenant_id: UUID,
        sku_code: str,
        price: int | float,
    ) -> ApprovalRequest:
        return await self._request_only(
            tenant_id=tenant_id,
            action=RiskyAction.change_price,
            payload={"sku_code": sku_code, "price": price},
        )

    async def change_inventory(
        self,
        *,
        tenant_id: UUID,
        sku_code: str,
        quantity: int,
    ) -> ApprovalRequest:
        return await self._request_only(
            tenant_id=tenant_id,
            action=RiskyAction.change_inventory,
            payload={"sku_code": sku_code, "quantity": quantity},
        )

    async def publish_douyin(
        self,
        *,
        tenant_id: UUID,
        content: str,
    ) -> ApprovalRequest:
        return await self._request_only(
            tenant_id=tenant_id,
            action=RiskyAction.publish_douyin,
            payload={"content": content},
        )
