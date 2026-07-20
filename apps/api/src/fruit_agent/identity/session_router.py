from typing import Annotated

from fastapi import APIRouter, Depends

from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.schemas import SessionRead, TenantPrincipal
from fruit_agent.identity.service import ROLE_PERMISSIONS

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get("/session", response_model=SessionRead)
async def read_session(
    principal: Annotated[TenantPrincipal, Depends(get_principal)],
) -> SessionRead:
    return SessionRead(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        role=principal.role,
        permissions=sorted(ROLE_PERMISSIONS[principal.role]),
    )
