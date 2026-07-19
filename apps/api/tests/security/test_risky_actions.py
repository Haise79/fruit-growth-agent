from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from fruit_agent.approvals.models import ApprovalRequest, RiskyAction
from fruit_agent.commerce.mock_douyin import DouyinShopAdapterMock


@pytest.mark.asyncio
async def test_all_risky_actions_have_no_execution_path() -> None:
    tenant_id = uuid4()
    actor_id = uuid4()
    approvals = AsyncMock()
    approvals.request.side_effect = lambda **kwargs: ApprovalRequest(
        tenant_id=kwargs["tenant_id"],
        requested_by=kwargs["actor_id"],
        action=kwargs["action"].value,
        payload=kwargs["payload"],
        requires_approval=True,
        status="pending",
    )
    adapter = DouyinShopAdapterMock(approvals=approvals, actor_id=actor_id)

    results = [
        await adapter.refund(
            tenant_id=tenant_id,
            order_id="O1",
            amount=10,
        ),
        await adapter.compensate(
            tenant_id=tenant_id,
            order_id="O1",
            amount=5,
        ),
        await adapter.change_price(
            tenant_id=tenant_id,
            sku_code="A1",
            price=20,
        ),
        await adapter.change_inventory(
            tenant_id=tenant_id,
            sku_code="A1",
            quantity=8,
        ),
        await adapter.publish_douyin(
            tenant_id=tenant_id,
            content="新鲜水果",
        ),
    ]

    assert {result.action for result in results} == {
        action.value for action in RiskyAction
    }
    assert all(result.requires_approval for result in results)
    assert all(result.status == "pending" for result in results)
    assert adapter.executed_actions == []
