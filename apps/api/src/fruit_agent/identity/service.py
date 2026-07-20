from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.identity.models import Membership, Role, User
from fruit_agent.identity.schemas import MemberCreate

logger = structlog.get_logger(__name__)

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.owner: frozenset(
        {
            "members:read",
            "members:write",
            "knowledge:read",
            "knowledge:write",
            "knowledge:review",
            "imports:write",
            "approval:request",
            "approval:decide",
            "audit:read",
        }
    ),
    Role.implementer: frozenset(
        {
            "members:read",
            "members:write",
            "knowledge:read",
            "knowledge:write",
            "knowledge:review",
            "imports:write",
            "audit:read",
        }
    ),
    Role.operator: frozenset(
        {
            "members:read",
            "knowledge:read",
            "knowledge:write",
            "imports:write",
            "approval:request",
        }
    ),
    Role.support: frozenset({"knowledge:read", "approval:request"}),
}


@dataclass(frozen=True, slots=True)
class MemberRecord:
    membership: Membership
    email: str


class DuplicateMemberError(ValueError):
    pass


def has_permission(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS[role]


async def list_members(
    session: AsyncSession,
    tenant_id: UUID,
) -> list[MemberRecord]:
    rows = await session.execute(
        select(Membership, User.email)
        .join(
            User,
            (User.tenant_id == Membership.tenant_id)
            & (User.id == Membership.user_id),
        )
        .where(
            Membership.tenant_id == tenant_id,
            User.tenant_id == tenant_id,
        )
        .order_by(User.email)
    )
    records = [
        MemberRecord(membership=membership, email=email)
        for membership, email in rows.all()
    ]
    await logger.ainfo(
        "members_listed",
        tenant_id=str(tenant_id),
        member_count=len(records),
    )
    return records


async def get_member(
    session: AsyncSession,
    tenant_id: UUID,
    membership_id: UUID,
) -> MemberRecord | None:
    row = (
        await session.execute(
            select(Membership, User.email)
            .join(
                User,
                (User.tenant_id == Membership.tenant_id)
                & (User.id == Membership.user_id),
            )
            .where(
                Membership.tenant_id == tenant_id,
                Membership.id == membership_id,
                User.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if row is None:
        await logger.awarning(
            "member_not_found",
            tenant_id=str(tenant_id),
            membership_id=str(membership_id),
        )
        return None
    membership, email = row
    return MemberRecord(membership=membership, email=email)


async def create_member(
    session: AsyncSession,
    tenant_id: UUID,
    member: MemberCreate,
) -> MemberRecord:
    existing_user = await session.scalar(
        select(User).where(
            User.tenant_id == tenant_id,
            User.email == member.email,
        )
    )
    if existing_user is not None:
        existing_membership = await session.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == existing_user.id,
            )
        )
        if existing_membership is not None:
            raise DuplicateMemberError("member already exists")
        user = existing_user
    else:
        user = User(tenant_id=tenant_id, email=str(member.email))
        session.add(user)
        await session.flush()

    membership = Membership(
        tenant_id=tenant_id,
        user_id=user.id,
        role=member.role.value,
    )
    session.add(membership)
    await session.flush()
    await logger.ainfo(
        "member_created",
        tenant_id=str(tenant_id),
        membership_id=str(membership.id),
        user_id=str(user.id),
        role=member.role.value,
    )
    return MemberRecord(membership=membership, email=user.email)
