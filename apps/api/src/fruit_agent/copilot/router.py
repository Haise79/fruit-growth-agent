from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.copilot.repository import CopilotRepository
from fruit_agent.copilot.schemas import (
    CopilotCaseCreate,
    CopilotCaseRead,
    CopilotSuggestionEdit,
    CopilotSuggestionRead,
)
from fruit_agent.copilot.service import CopilotService
from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.model_gateway.router import get_provider_bindings
from fruit_agent.model_gateway.service import ProviderBinding

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])


def _service(
    session: AsyncSession,
    providers: list[ProviderBinding],
) -> CopilotService:
    return CopilotService(
        repository=CopilotRepository(session),
        knowledge_repository=KnowledgeRepository(session),
        providers=providers,
    )


@router.post(
    "/cases",
    response_model=CopilotCaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_case(
    body: CopilotCaseCreate,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("copilot:use")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[
        list[ProviderBinding],
        Depends(get_provider_bindings),
    ],
) -> CopilotCaseRead:
    async with tenant_session(session, principal.tenant_id):
        service = _service(session, providers)
        case = await service.create_case(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            request=body,
        )
        loaded_case = await service.get_case(principal.tenant_id, case.id)
        if loaded_case is None:
            raise RuntimeError("newly created copilot case was not found")
        response = CopilotCaseRead.model_validate(loaded_case)
    return response


@router.get("/cases", response_model=list[CopilotCaseRead])
async def list_cases(
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("copilot:use")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[
        list[ProviderBinding],
        Depends(get_provider_bindings),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CopilotCaseRead]:
    async with tenant_session(session, principal.tenant_id):
        cases = await _service(session, providers).list_cases(
            principal.tenant_id,
            limit=limit,
            offset=offset,
        )
        response = [
            CopilotCaseRead.model_validate(case)
            for case in cases
        ]
    return response


@router.get("/cases/{case_id}", response_model=CopilotCaseRead)
async def get_case(
    case_id: UUID,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("copilot:use")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[
        list[ProviderBinding],
        Depends(get_provider_bindings),
    ],
) -> CopilotCaseRead:
    async with tenant_session(session, principal.tenant_id):
        case = await _service(session, providers).get_case(
            principal.tenant_id,
            case_id,
        )
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="copilot case not found",
            )
        response = CopilotCaseRead.model_validate(case)
    return response


@router.patch(
    "/cases/{case_id}/suggestions/{suggestion_id}",
    response_model=CopilotSuggestionRead,
)
async def edit_suggestion(
    case_id: UUID,
    suggestion_id: UUID,
    body: CopilotSuggestionEdit,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("copilot:use")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[
        list[ProviderBinding],
        Depends(get_provider_bindings),
    ],
) -> CopilotSuggestionRead:
    async with tenant_session(session, principal.tenant_id):
        suggestion = await _service(session, providers).edit_suggestion(
            tenant_id=principal.tenant_id,
            case_id=case_id,
            suggestion_id=suggestion_id,
            edited_text=body.edited_text,
        )
        if suggestion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="copilot suggestion not found",
            )
        response = CopilotSuggestionRead.model_validate(suggestion)
    return response
