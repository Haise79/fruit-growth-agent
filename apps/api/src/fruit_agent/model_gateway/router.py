from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.model_gateway.schemas import (
    GatewaySuggestion,
    SuggestionRequest,
)
from fruit_agent.model_gateway.service import (
    ModelGateway,
    ProviderBinding,
    ProviderUnavailableError,
)

router = APIRouter(prefix="/api/v1/model-gateway", tags=["model-gateway"])


def get_provider_bindings(request: Request) -> list[ProviderBinding]:
    bindings = getattr(request.app.state, "model_providers", [])
    return cast(list[ProviderBinding], bindings)


@router.post("/suggestions", response_model=GatewaySuggestion)
async def create_suggestion(
    body: SuggestionRequest,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:read")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[
        list[ProviderBinding],
        Depends(get_provider_bindings),
    ],
) -> GatewaySuggestion:
    if not providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="no model providers configured",
        )
    try:
        async with tenant_session(session, principal.tenant_id):
            return await ModelGateway(
                session=session,
                providers=providers,
            ).suggest(
                tenant_id=principal.tenant_id,
                prompt=body.prompt,
            )
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="model providers unavailable",
        ) from exc
