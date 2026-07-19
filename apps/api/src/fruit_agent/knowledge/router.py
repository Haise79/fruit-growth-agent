from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.schemas import ExactFactResult
from fruit_agent.knowledge.service import KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


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
