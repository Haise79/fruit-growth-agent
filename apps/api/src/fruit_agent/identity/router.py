from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.audit.middleware import get_request_id
from fruit_agent.audit.service import AuditService
from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.models import MembershipStatus, Role
from fruit_agent.identity.schemas import (
    MemberCreate,
    MemberRead,
    TenantPrincipal,
)
from fruit_agent.identity.service import (
    DuplicateMemberError,
    MemberRecord,
    create_member,
    get_member,
    list_members,
)

router = APIRouter(prefix="/api/v1/members", tags=["members"])


def _to_member_read(record: MemberRecord) -> MemberRead:
    membership = record.membership
    return MemberRead(
        id=membership.id,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        email=record.email,
        role=Role(membership.role),
        status=MembershipStatus(membership.status),
    )


@router.get("", response_model=list[MemberRead])
async def read_members(
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("members:read")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MemberRead]:
    async with tenant_session(session, principal.tenant_id):
        records = await list_members(session, principal.tenant_id)
    return [_to_member_read(record) for record in records]


@router.get("/{membership_id}", response_model=MemberRead)
async def read_member(
    membership_id: UUID,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("members:read")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemberRead:
    async with tenant_session(session, principal.tenant_id):
        record = await get_member(session, principal.tenant_id, membership_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    return _to_member_read(record)


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
async def write_member(
    member: MemberCreate,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("members:write")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemberRead:
    try:
        async with tenant_session(session, principal.tenant_id):
            record = await create_member(session, principal.tenant_id, member)
            await AuditService(
                session=session,
                principal=principal,
                request_id=get_request_id(),
            ).record(
                action="member.created",
                entity_type="membership",
                entity_id=record.membership.id,
                before={},
                after={
                    "email": record.email,
                    "role": record.membership.role,
                    "status": record.membership.status,
                },
            )
    except DuplicateMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _to_member_read(record)
