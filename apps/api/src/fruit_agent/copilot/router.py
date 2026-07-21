from typing import Annotated
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.audit.middleware import get_request_id
from fruit_agent.audit.service import AuditService
from fruit_agent.copilot.repository import CopilotRepository
from fruit_agent.copilot.schemas import (
    CopilotCaseCreate,
    CopilotCaseRead,
    CopilotOutcomeEventCreate,
    CopilotOutcomeEventRead,
    CopilotOutcomeEventType,
    CopilotCaseStatus,
    CopilotSuggestionEdit,
    CopilotSuggestionRead,
)
from fruit_agent.copilot.service import CopilotService
from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.dependencies import get_embedding_provider
from fruit_agent.knowledge.embeddings import EmbeddingProvider
from fruit_agent.model_gateway.router import get_provider_bindings
from fruit_agent.model_gateway.service import ProviderBinding

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])


def _service(
    session: AsyncSession,
    providers: list[ProviderBinding],
    embedding_provider: EmbeddingProvider | None = None,
) -> CopilotService:
    return CopilotService(
        repository=CopilotRepository(session),
        knowledge_repository=KnowledgeRepository(session),
        providers=providers,
        embedding_provider=embedding_provider,
    )


@router.post(
    "/cases",
    response_model=CopilotCaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_case(
    body: CopilotCaseCreate,
    http_request: Request,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("copilot:use")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[
        list[ProviderBinding],
        Depends(get_provider_bindings),
    ],
    embedding_provider: Annotated[
        EmbeddingProvider | None,
        Depends(get_embedding_provider),
    ],
) -> CopilotCaseRead:
    async with tenant_session(session, principal.tenant_id):
        started_at = perf_counter()
        service = _service(session, providers, embedding_provider)
        case = await service.create_case(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            request=body,
        )
        loaded_case = await service.get_case(principal.tenant_id, case.id)
        if loaded_case is None:
            raise RuntimeError("newly created copilot case was not found")
        loaded_case.response_time_ms = max(
            0,
            round((perf_counter() - started_at) * 1000),
        )
        await service.repository.flush()
        await session.refresh(
            loaded_case,
            attribute_names=["response_time_ms", "updated_at"],
        )
        response = CopilotCaseRead.model_validate(loaded_case)
        await AuditService(
            session=session,
            principal=principal,
            request_id=getattr(
                http_request.state,
                "request_id",
                get_request_id(),
            ),
        ).record(
            action="copilot_case.created",
            entity_type="copilot_case",
            entity_id=case.id,
            before={},
            after=response.model_dump(mode="json"),
        )
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
    http_request: Request,
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
        service = _service(session, providers)
        existing = await service.repository.get_suggestion(
            principal.tenant_id,
            case_id,
            suggestion_id,
        )
        before = (
            CopilotSuggestionRead.model_validate(existing).model_dump(mode="json")
            if existing is not None
            else {}
        )
        suggestion = await service.edit_suggestion(
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
        await AuditService(
            session=session,
            principal=principal,
            request_id=getattr(
                http_request.state,
                "request_id",
                get_request_id(),
            ),
        ).record(
            action="copilot_suggestion.edited",
            entity_type="copilot_suggestion",
            entity_id=suggestion.id,
            before=before,
            after=response.model_dump(mode="json"),
        )
    return response


@router.post(
    "/cases/{case_id}/events",
    response_model=CopilotOutcomeEventRead,
    status_code=status.HTTP_201_CREATED,
)
async def record_outcome_event(
    case_id: UUID,
    body: CopilotOutcomeEventCreate,
    http_request: Request,
    idempotency_key: Annotated[
        str,
        Header(min_length=1, max_length=200),
    ],
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("copilot:use")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    providers: Annotated[
        list[ProviderBinding],
        Depends(get_provider_bindings),
    ],
) -> CopilotOutcomeEventRead:
    if not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Idempotency-Key may not be blank",
        )
    async with tenant_session(session, principal.tenant_id):
        result = await _service(session, providers).record_outcome_event(
            tenant_id=principal.tenant_id,
            case_id=case_id,
            idempotency_key=idempotency_key,
            request=body,
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="copilot case or suggestion not found",
            )
        event, case, duplicate = result
        if not duplicate:
            await AuditService(
                session=session,
                principal=principal,
                request_id=getattr(http_request.state, "request_id", get_request_id()),
            ).record(
                action="copilot_outcome_recorded",
                entity_type="copilot_outcome_event",
                entity_id=event.id,
                before={},
                after={
                    "case_id": str(event.case_id),
                    "suggestion_id": (
                        str(event.suggestion_id)
                        if event.suggestion_id is not None
                        else None
                    ),
                    "event_type": event.event_type,
                    "metadata": event.metadata_,
                },
            )
        response = CopilotOutcomeEventRead(
            id=event.id,
            case_id=event.case_id,
            suggestion_id=event.suggestion_id,
            event_type=CopilotOutcomeEventType(event.event_type),
            occurred_at=event.occurred_at,
            metadata=event.metadata_,
            created_at=event.created_at,
            case_status=CopilotCaseStatus(case.status),
        )
    return response
