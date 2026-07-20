from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.config import get_settings
from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.models import Membership, MembershipStatus, Role
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.identity.service import has_permission

logger = structlog.get_logger(__name__)
bearer = HTTPBearer()


async def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TenantPrincipal:
    settings = get_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_public_key,
            algorithms=["RS256"],
            audience=settings.jwt_audience,
        )
        claimed_tenant_id = UUID(claims["tenant_id"])
        claimed_user_id = UUID(claims["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        await logger.awarning("authentication_failed", reason=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid authentication token",
        ) from exc

    async with tenant_session(session, claimed_tenant_id):
        membership = await session.scalar(
            select(Membership).where(
                Membership.tenant_id == claimed_tenant_id,
                Membership.user_id == claimed_user_id,
                Membership.status == MembershipStatus.active.value,
            )
        )
    if membership is None:
        await logger.awarning(
            "tenant_membership_rejected",
            tenant_id=str(claimed_tenant_id),
            user_id=str(claimed_user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid tenant membership",
        )

    try:
        role = Role(membership.role)
    except ValueError as exc:
        await logger.aerror(
            "invalid_membership_role",
            tenant_id=str(claimed_tenant_id),
            user_id=str(claimed_user_id),
            role=membership.role,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid tenant membership",
        ) from exc
    return TenantPrincipal(
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=role,
    )


PermissionDependency = Callable[
    [TenantPrincipal],
    Coroutine[Any, Any, TenantPrincipal],
]


def require_permissions(*permissions: str) -> PermissionDependency:
    async def permission_dependency(
        principal: Annotated[TenantPrincipal, Depends(get_principal)],
    ) -> TenantPrincipal:
        denied = [
            permission
            for permission in permissions
            if not has_permission(principal.role, permission)
        ]
        if denied:
            await logger.awarning(
                "permission_denied",
                tenant_id=str(principal.tenant_id),
                user_id=str(principal.user_id),
                role=principal.role.value,
                required_permissions=list(permissions),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient permissions",
            )
        return principal

    return permission_dependency
