from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.dependencies import get_embedding_provider
from fruit_agent.knowledge.embeddings import EmbeddingProvider
from fruit_agent.knowledge.models import ReviewStatus
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
    if embedding_provider is None:
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
    except InvalidResponsibleUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return KnowledgeItemRead.model_validate(record)


@router.patch("/items/{knowledge_id}", response_model=KnowledgeItemRead)
async def update_knowledge_item(
    knowledge_id: UUID,
    changes: KnowledgeItemUpdate,
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
    if embedding_provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedding provider is not configured",
        )
    try:
        async with tenant_session(session, principal.tenant_id):
            record = await KnowledgeService(
                KnowledgeRepository(session),
                embedding_provider,
            ).update_item(
                tenant_id=principal.tenant_id,
                knowledge_id=knowledge_id,
                changes=changes,
            )
    except InvalidResponsibleUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge not found")
    return KnowledgeItemRead.model_validate(record)


@router.post("/items/{knowledge_id}/review", response_model=KnowledgeItemRead)
async def review_knowledge_item(
    knowledge_id: UUID,
    review: KnowledgeReviewRequest,
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("knowledge:review")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KnowledgeItemRead:
    async with tenant_session(session, principal.tenant_id):
        record = await KnowledgeService(KnowledgeRepository(session)).review_item(
            tenant_id=principal.tenant_id,
            knowledge_id=knowledge_id,
            review_status=ReviewStatus(review.review_status),
        )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge not found")
    return KnowledgeItemRead.model_validate(record)


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
