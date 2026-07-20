from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.audit.middleware import get_request_id
from fruit_agent.audit.service import AuditService
from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.dependencies import get_embedding_provider
from fruit_agent.knowledge.embeddings import (
    EmbeddingProvider,
    embedding_provider_is_allowed,
)
from fruit_agent.knowledge.models import KnowledgeType, ReviewStatus
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.schemas import (
    ExactFactResult,
    KnowledgeItemCreate,
    KnowledgeItemRead,
    KnowledgeItemUpdate,
    KnowledgeReviewRequest,
)
from fruit_agent.knowledge.service import (
    InvalidResponsibleUserError,
    KnowledgeService,
)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.get("/items/search", response_model=list[KnowledgeItemRead])
async def search_knowledge_items(
    q: Annotated[str, Query(min_length=1, max_length=1000)],
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:write")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    embedding_provider: Annotated[
        EmbeddingProvider | None,
        Depends(get_embedding_provider),
    ],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[KnowledgeItemRead]:
    if embedding_provider is None or not embedding_provider_is_allowed(
        embedding_provider
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedding provider is not configured",
        )
    async with tenant_session(session, principal.tenant_id):
        records = await KnowledgeRepository(session).search_semantic(
            tenant_id=principal.tenant_id,
            query_embedding=embedding_provider.embed(q),
            knowledge_types=[
                KnowledgeType.faq,
                KnowledgeType.talking_point,
                KnowledgeType.origin_story,
            ],
            now=datetime.now(UTC),
            limit=limit,
            embedding_model=embedding_provider.model_name,
            embedding_version=embedding_provider.model_version,
        )
    return [KnowledgeItemRead.model_validate(record) for record in records]


@router.get("/items", response_model=list[KnowledgeItemRead])
async def list_knowledge_items(
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:read")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[KnowledgeItemRead]:
    async with tenant_session(session, principal.tenant_id):
        records = await KnowledgeService(KnowledgeRepository(session)).list_items(
            principal.tenant_id
        )
    return [KnowledgeItemRead.model_validate(record) for record in records]


@router.post(
    "/items",
    response_model=KnowledgeItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_item(
    item: KnowledgeItemCreate,
    http_request: Request,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:write")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    embedding_provider: Annotated[
        EmbeddingProvider | None,
        Depends(get_embedding_provider),
    ],
) -> KnowledgeItemRead:
    if embedding_provider is None or not embedding_provider_is_allowed(
        embedding_provider
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedding provider is not configured",
        )
    try:
        async with tenant_session(session, principal.tenant_id):
            record = await KnowledgeService(
                KnowledgeRepository(session),
                embedding_provider,
            ).create_item(
                tenant_id=principal.tenant_id,
                item=item,
            )
            response = KnowledgeItemRead.model_validate(record)
            await AuditService(
                session=session,
                principal=principal,
                request_id=getattr(
                    http_request.state,
                    "request_id",
                    get_request_id(),
                ),
            ).record(
                action="knowledge.created",
                entity_type="merchant_knowledge",
                entity_id=record.id,
                before={},
                after=response.model_dump(mode="json"),
            )
    except InvalidResponsibleUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return response


@router.patch("/items/{knowledge_id}", response_model=KnowledgeItemRead)
async def update_knowledge_item(
    knowledge_id: UUID,
    changes: KnowledgeItemUpdate,
    http_request: Request,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:write")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    embedding_provider: Annotated[
        EmbeddingProvider | None,
        Depends(get_embedding_provider),
    ],
) -> KnowledgeItemRead:
    if embedding_provider is None or not embedding_provider_is_allowed(
        embedding_provider
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedding provider is not configured",
        )
    try:
        async with tenant_session(session, principal.tenant_id):
            repository = KnowledgeRepository(session)
            existing = await repository.get_item(
                principal.tenant_id,
                knowledge_id,
            )
            before = (
                KnowledgeItemRead.model_validate(existing).model_dump(mode="json")
                if existing is not None
                else {}
            )
            record = await KnowledgeService(
                repository,
                embedding_provider,
            ).update_item(
                tenant_id=principal.tenant_id,
                knowledge_id=knowledge_id,
                changes=changes,
            )
            if record is not None:
                response = KnowledgeItemRead.model_validate(record)
                await AuditService(
                    session=session,
                    principal=principal,
                    request_id=getattr(
                        http_request.state,
                        "request_id",
                        get_request_id(),
                    ),
                ).record(
                    action="knowledge.updated",
                    entity_type="merchant_knowledge",
                    entity_id=record.id,
                    before=before,
                    after=response.model_dump(mode="json"),
                )
    except InvalidResponsibleUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge not found")
    return response


@router.post("/items/{knowledge_id}/review", response_model=KnowledgeItemRead)
async def review_knowledge_item(
    knowledge_id: UUID,
    review: KnowledgeReviewRequest,
    http_request: Request,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:review")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KnowledgeItemRead:
    async with tenant_session(session, principal.tenant_id):
        repository = KnowledgeRepository(session)
        existing = await repository.get_item(principal.tenant_id, knowledge_id)
        before = (
            KnowledgeItemRead.model_validate(existing).model_dump(mode="json")
            if existing is not None
            else {}
        )
        record = await KnowledgeService(repository).review_item(
            tenant_id=principal.tenant_id,
            knowledge_id=knowledge_id,
            review_status=ReviewStatus(review.review_status),
        )
        if record is not None:
            response = KnowledgeItemRead.model_validate(record)
            await AuditService(
                session=session,
                principal=principal,
                request_id=getattr(
                    http_request.state,
                    "request_id",
                    get_request_id(),
                ),
            ).record(
                action="knowledge.reviewed",
                entity_type="merchant_knowledge",
                entity_id=record.id,
                before=before,
                after=response.model_dump(mode="json"),
            )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge not found")
    return response


@router.get("/skus/{sku_code}", response_model=ExactFactResult)
async def get_sku_fact(
    sku_code: str,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:read")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExactFactResult:
    async with tenant_session(session, principal.tenant_id):
        return await KnowledgeService(
            KnowledgeRepository(session)
        ).get_recommendable_sku(
            tenant_id=principal.tenant_id,
            sku_code=sku_code,
        )
