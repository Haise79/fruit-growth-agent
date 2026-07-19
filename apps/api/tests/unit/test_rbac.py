from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Role
from fruit_agent.identity.service import has_permission


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.owner, "members:write", True),
        (Role.implementer, "members:write", True),
        (Role.operator, "members:write", False),
        (Role.support, "knowledge:read", True),
        (Role.support, "knowledge:write", False),
    ],
)
def test_role_permissions(role: Role, permission: str, allowed: bool) -> None:
    assert has_permission(role, permission) is allowed


@pytest.mark.asyncio
async def test_principal_rejects_non_rs256_token() -> None:
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "aud": "fruit-agent-api",
        },
        "untrusted-secret-that-is-at-least-32-bytes",
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(HTTPException) as exc_info:
        await get_principal(credentials, session)

    assert exc_info.value.status_code == 401
