from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.audit.middleware import get_request_id
from fruit_agent.audit.service import AuditService
from fruit_agent.db import get_session, tenant_session
from fruit_agent.identity.dependencies import require_permissions
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.imports.manual import ImportFormatError, ManualImportAdapter
from fruit_agent.imports.schemas import ImportResult

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])
MAX_CSV_BYTES = 5 * 1024 * 1024


@router.post("/products", response_model=ImportResult)
async def import_products(
    file: Annotated[UploadFile, File()],
    principal: Annotated[
        TenantPrincipal,
        Depends(require_permissions("imports:write")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportResult:
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="CSV file exceeds 5 MiB",
        )
    try:
        async with tenant_session(session, principal.tenant_id):
            result = await ManualImportAdapter(session).import_products(
                tenant_id=principal.tenant_id,
                content=content,
            )
            await AuditService(
                session=session,
                principal=principal,
                request_id=get_request_id(),
            ).record(
                action="products.imported",
                entity_type="product_import",
                entity_id=uuid4(),
                before={},
                after=result.model_dump(mode="json"),
            )
    except ImportFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return result
