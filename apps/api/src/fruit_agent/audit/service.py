from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.audit.models import AuditEvent
from fruit_agent.common.redaction import redact
from fruit_agent.identity.schemas import TenantPrincipal

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        principal: TenantPrincipal,
        request_id: str,
    ) -> None:
        self._session = session
        self._principal = principal
        self._request_id = request_id

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: UUID,
        before: object,
        after: object,
    ) -> AuditEvent:
        event = AuditEvent(
            tenant_id=self._principal.tenant_id,
            actor_id=self._principal.user_id,
            request_id=self._request_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=redact(before),
            after=redact(after),
        )
        self._session.add(event)
        await self._session.flush()
        await logger.ainfo(
            "audit_event_recorded",
            tenant_id=str(self._principal.tenant_id),
            actor_id=str(self._principal.user_id),
            request_id=self._request_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
        )
        return event
