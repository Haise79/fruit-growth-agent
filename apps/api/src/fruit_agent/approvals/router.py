from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.approvals.models import ApprovalRequest, ApprovalStatus
from fruit_agent.approvals.schemas import (
    ApprovalCreate,
    ApprovalDecision,
    ApprovalRead,
)
from fruit_agent.approvals.service import (
    ApprovalNotFoundError,
    ApprovalService,
)
from fruit_agent.audit.middleware import get_request_id
from fruit_agent.audit.service import AuditService
from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _to_read(item: ApprovalRequest) -> ApprovalRead:
    return ApprovalRead.model_validate(item)


@router.post("", response_model=ApprovalRead, status_code=status.HTTP_201_CREATED)
async def request_approval(
    approval: ApprovalCreate,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("approval:request")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApprovalRead:
    async with tenant_session(session, principal.tenant_id):
        item = await ApprovalService(session).request(
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action=approval.action,
            payload=approval.payload,
        )
        await AuditService(
            session=session,
            principal=principal,
            request_id=get_request_id(),
        ).record(
            action="approval.requested",
            entity_type="approval_request",
            entity_id=item.id,
            before={},
            after={
                "action": item.action,
                "status": item.status,
                "requires_approval": item.requires_approval,
            },
        )
    return _to_read(item)


@router.post("/{approval_id}/decision", response_model=ApprovalRead)
async def decide_approval(
    approval_id: UUID,
    decision: ApprovalDecision,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("approval:decide")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApprovalRead:
    try:
        async with tenant_session(session, principal.tenant_id):
            item = await ApprovalService(session).decide(
                tenant_id=principal.tenant_id,
                actor_id=principal.user_id,
                approval_id=approval_id,
                decision=ApprovalStatus(decision.decision),
            )
            await AuditService(
                session=session,
                principal=principal,
                request_id=get_request_id(),
            ).record(
                action="approval.decided",
                entity_type="approval_request",
                entity_id=item.id,
                before={"status": ApprovalStatus.pending.value},
                after={"status": item.status},
            )
    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _to_read(item)
