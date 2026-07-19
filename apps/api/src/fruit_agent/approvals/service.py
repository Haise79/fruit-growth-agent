from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.approvals.models import (
    ApprovalRequest,
    ApprovalStatus,
    RiskyAction,
)
from fruit_agent.common.redaction import redact

logger = structlog.get_logger(__name__)


class ApprovalNotFoundError(LookupError):
    pass


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        action: RiskyAction,
        payload: dict[str, object],
    ) -> ApprovalRequest:
        redacted_payload = redact(payload)
        if not isinstance(redacted_payload, dict):
            raise TypeError("approval payload must be an object")
        item = ApprovalRequest(
            tenant_id=tenant_id,
            requested_by=actor_id,
            action=action.value,
            payload=redacted_payload,
            requires_approval=True,
            status=ApprovalStatus.pending.value,
        )
        self.session.add(item)
        await self.session.flush()
        await logger.ainfo(
            "approval_requested",
            tenant_id=str(tenant_id),
            requested_by=str(actor_id),
            approval_id=str(item.id),
            action=action.value,
            status=ApprovalStatus.pending.value,
        )
        return item

    async def decide(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        approval_id: UUID,
        decision: ApprovalStatus,
    ) -> ApprovalRequest:
        if decision is ApprovalStatus.pending:
            raise ValueError("decision must be approved or rejected")
        item = await self.session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == tenant_id,
                ApprovalRequest.id == approval_id,
                ApprovalRequest.status == ApprovalStatus.pending.value,
            )
        )
        if item is None:
            raise ApprovalNotFoundError("approval request not found")
        item.status = decision.value
        item.decided_by = actor_id
        item.decided_at = datetime.now(UTC)
        await self.session.flush()
        await logger.ainfo(
            "approval_decided",
            tenant_id=str(tenant_id),
            decided_by=str(actor_id),
            approval_id=str(approval_id),
            decision=decision.value,
        )
        return item
