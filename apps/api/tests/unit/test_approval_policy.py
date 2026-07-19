from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.approvals.models import ApprovalStatus, RiskyAction
from fruit_agent.approvals.service import ApprovalService


@pytest.mark.asyncio
@pytest.mark.parametrize("action", list(RiskyAction))
async def test_risky_action_only_creates_pending_request(
    action: RiskyAction,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    approval_service = ApprovalService(session)

    request = await approval_service.request(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        action=action,
        payload={"amount": 100, "receiver_phone": "13800138000"},
    )

    assert request.requires_approval is True
    assert request.status == ApprovalStatus.pending.value
    assert request.payload["receiver_phone"] == "[REDACTED]"
    session.add.assert_called_once_with(request)
    session.flush.assert_awaited_once()
