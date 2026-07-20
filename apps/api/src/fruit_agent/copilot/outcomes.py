from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fruit_agent.common.models import Base, TenantOwnedMixin


class CopilotOutcomeEvent(TenantOwnedMixin, Base):
    __tablename__ = "copilot_outcome_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "case_id"),
            ("copilot_cases.tenant_id", "copilot_cases.id"),
            name="fk_copilot_outcomes_tenant_case",
        ),
        ForeignKeyConstraint(
            ("tenant_id", "suggestion_id"),
            ("copilot_suggestions.tenant_id", "copilot_suggestions.id"),
            name="fk_copilot_outcomes_tenant_suggestion",
        ),
        UniqueConstraint(
            "tenant_id",
            "case_id",
            "idempotency_key",
            name="uq_copilot_outcomes_tenant_case_idempotency",
        ),
        CheckConstraint(
            "event_type IN ('suggestion_adopted', 'suggestion_rejected', "
            "'payment', 'refund', 'complaint', 'case_closed')",
            name="ck_copilot_outcomes_event_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    suggestion_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
