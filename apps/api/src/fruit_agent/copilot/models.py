from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fruit_agent.common.models import Base, TenantOwnedMixin


class CopilotCase(TenantOwnedMixin, Base):
    __tablename__ = "copilot_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "created_by_user_id"),
            ("users.tenant_id", "users.id"),
            name="fk_copilot_cases_tenant_creator",
        ),
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_copilot_cases_tenant_id_id",
        ),
        CheckConstraint(
            "stage IN ('presale', 'aftersale', 'unknown')",
            name="ck_copilot_cases_stage",
        ),
        CheckConstraint(
            "intent IN ('product_info', 'recommendation', 'gift', "
            "'delivery', 'storage', 'damage', 'refund', 'complaint', "
            "'health_safety', 'other')",
            name="ck_copilot_cases_intent",
        ),
        CheckConstraint(
            "risk IN ('low', 'medium', 'high', 'critical')",
            name="ck_copilot_cases_risk",
        ),
        CheckConstraint(
            "status IN ('suggestions_ready', 'handoff_required', "
            "'degraded', 'closed')",
            name="ck_copilot_cases_status",
        ),
        CheckConstraint(
            "response_time_ms >= 0",
            name="ck_copilot_cases_response_time_ms",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_by_user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(4000), nullable=False)
    selected_sku_codes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    intent: Mapped[str] = mapped_column(String(32), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_reasons: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    response_time_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    handoff_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    conflict_source_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    suggestions: Mapped[list[CopilotSuggestion]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CopilotSuggestion.rank",
        lazy="selectin",
    )


class CopilotSuggestion(TenantOwnedMixin, Base):
    __tablename__ = "copilot_suggestions"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "case_id"),
            ("copilot_cases.tenant_id", "copilot_cases.id"),
            name="fk_copilot_suggestions_tenant_case",
        ),
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_copilot_suggestions_tenant_id_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "case_id",
            "id",
            name="uq_copilot_suggestions_tenant_case_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "case_id",
            "rank",
            name="uq_copilot_suggestions_tenant_case_rank",
        ),
        CheckConstraint(
            "rank BETWEEN 1 AND 3",
            name="ck_copilot_suggestions_rank",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_copilot_suggestions_confidence",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    original_text: Mapped[str] = mapped_column(String(4000), nullable=False)
    edited_text: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_sku_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tip: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    degraded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    case: Mapped[CopilotCase] = relationship(back_populates="suggestions")
    citations: Mapped[list[CopilotCitationSnapshot]] = relationship(
        back_populates="suggestion",
        cascade="all, delete-orphan",
        order_by="CopilotCitationSnapshot.created_at",
        lazy="selectin",
    )


class CopilotCitationSnapshot(TenantOwnedMixin, Base):
    __tablename__ = "copilot_citation_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "suggestion_id"),
            ("copilot_suggestions.tenant_id", "copilot_suggestions.id"),
            name="fk_copilot_citations_tenant_suggestion",
        ),
        CheckConstraint(
            "citation_type IN ('sku', 'knowledge')",
            name="ck_copilot_citations_type",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    suggestion_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    citation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[UUID] = mapped_column(nullable=False)
    source_name: Mapped[str] = mapped_column(String(300), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    suggestion: Mapped[CopilotSuggestion] = relationship(back_populates="citations")
