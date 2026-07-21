"""Add server timing, citation provenance, and persisted conflict context.

Revision ID: 0009_case_provenance
Revises: 0008_final_safety_invariants
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_case_provenance"
down_revision: str | None = "0008_final_safety_invariants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "copilot_cases",
        sa.Column(
            "response_time_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "copilot_cases",
        sa.Column("handoff_reason", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "copilot_cases",
        sa.Column(
            "conflict_source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "ck_copilot_cases_response_time_ms",
        "copilot_cases",
        "response_time_ms >= 0",
    )

    op.add_column(
        "copilot_citation_snapshots",
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "copilot_citation_snapshots",
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE copilot_citation_snapshots "
        "SET source_updated_at = created_at, retrieved_at = created_at"
    )
    op.alter_column(
        "copilot_citation_snapshots",
        "source_updated_at",
        nullable=False,
    )
    op.alter_column(
        "copilot_citation_snapshots",
        "retrieved_at",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("copilot_citation_snapshots", "retrieved_at")
    op.drop_column("copilot_citation_snapshots", "source_updated_at")
    op.drop_constraint(
        "ck_copilot_cases_response_time_ms",
        "copilot_cases",
        type_="check",
    )
    op.drop_column("copilot_cases", "conflict_source_ids")
    op.drop_column("copilot_cases", "handoff_reason")
    op.drop_column("copilot_cases", "response_time_ms")
