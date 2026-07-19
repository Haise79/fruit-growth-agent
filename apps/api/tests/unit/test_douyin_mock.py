from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from fruit_agent.approvals.models import (
    ApprovalRequest,
    ApprovalStatus,
    RiskyAction,
)
from fruit_agent.commerce.mock_douyin import DouyinShopAdapterMock


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "action", "kwargs"),
    [
        (
            "refund",
            RiskyAction.refund,
            {"order_id": "ORDER-1", "amount": 100},
        ),
        (
            "compensate",
            RiskyAction.compensate,
            {"order_id": "ORDER-1", "amount": 20},
        ),
        (
            "change_price",
            RiskyAction.change_price,
            {"sku_code": "A1", "price": 29.9},
        ),
        (
            "change_inventory",
            RiskyAction.change_inventory,
            {"sku_code": "A1", "quantity": 5},
        ),
        (
            "publish_douyin",
            RiskyAction.publish_douyin,
            {"content": "今日鲜果推荐"},
        ),
    ],
)
async def test_risky_douyin_writes_create_approval_only(
    method_name: str,
    action: RiskyAction,
    kwargs: dict[str, object],
) -> None:
    tenant_id = uuid4()
    actor_id = uuid4()
    approvals = AsyncMock()
    approvals.request.return_value = ApprovalRequest(
        tenant_id=tenant_id,
        requested_by=actor_id,
        action=action.value,
        payload=kwargs,
        requires_approval=True,
        status=ApprovalStatus.pending.value,
    )
    adapter = DouyinShopAdapterMock(approvals=approvals, actor_id=actor_id)

    method = getattr(adapter, method_name)
    result = await method(tenant_id=tenant_id, **kwargs)

    assert result.status == ApprovalStatus.pending.value
    assert result.requires_approval is True
    assert adapter.executed_actions == []
    approvals.request.assert_awaited_once_with(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        payload=kwargs,
    )
