"""Create copilot cases, suggestions, and immutable citation snapshots.

Revision ID: 0006_copilot_cases
Revises: 0005_knowledge_management
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_copilot_cases"
down_revision: str | None = "0005_knowledge_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_lifecycle_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "audit_log",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    ]


def _enable_rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON "{table}"
        USING (
            tenant_id
            = nullif(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id
            = nullif(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )


def upgrade() -> None:
    op.create_table(
        "copilot_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("message", sa.String(length=4000), nullable=False),
        sa.Column(
            "selected_sku_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=False),
        sa.Column("risk", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "risk_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        *_tenant_lifecycle_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_copilot_cases_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_copilot_cases_tenant_creator",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_copilot_cases_tenant_id_id",
        ),
    )
    op.create_index("ix_copilot_cases_tenant_id", "copilot_cases", ["tenant_id"])
    op.create_index(
        "ix_copilot_cases_created_by_user_id",
        "copilot_cases",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_copilot_cases_tenant_created_at",
        "copilot_cases",
        ["tenant_id", "created_at"],
    )
    _enable_rls("copilot_cases")

    op.create_table(
        "copilot_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("original_text", sa.String(length=4000), nullable=False),
        sa.Column("edited_text", sa.String(length=4000), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("recommended_sku_code", sa.String(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_tip", sa.String(length=1000), nullable=True),
        sa.Column(
            "degraded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("model_name", sa.String(length=200), nullable=True),
        *_tenant_lifecycle_columns(),
        sa.CheckConstraint("rank BETWEEN 1 AND 3", name="ck_copilot_suggestions_rank"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_copilot_suggestions_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_copilot_suggestions_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["copilot_cases.tenant_id", "copilot_cases.id"],
            name="fk_copilot_suggestions_tenant_case",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_copilot_suggestions_tenant_id_id",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "rank",
            name="uq_copilot_suggestions_tenant_case_rank",
        ),
    )
    op.create_index(
        "ix_copilot_suggestions_tenant_id",
        "copilot_suggestions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_copilot_suggestions_case_id",
        "copilot_suggestions",
        ["case_id"],
    )
    _enable_rls("copilot_suggestions")

    op.create_table(
        "copilot_citation_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("citation_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=300), nullable=False),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        *_tenant_lifecycle_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_copilot_citations_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "suggestion_id"],
            ["copilot_suggestions.tenant_id", "copilot_suggestions.id"],
            name="fk_copilot_citations_tenant_suggestion",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_copilot_citation_snapshots_tenant_id",
        "copilot_citation_snapshots",
        ["tenant_id"],
    )
    op.create_index(
        "ix_copilot_citation_snapshots_suggestion_id",
        "copilot_citation_snapshots",
        ["suggestion_id"],
    )
    _enable_rls("copilot_citation_snapshots")

    op.execute(
        """
        CREATE FUNCTION reject_copilot_citation_snapshot_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'copilot citation snapshots are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER copilot_citation_snapshots_immutable
        BEFORE UPDATE OR DELETE ON copilot_citation_snapshots
        FOR EACH ROW
        EXECUTE FUNCTION reject_copilot_citation_snapshot_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER copilot_citation_snapshots_immutable "
        "ON copilot_citation_snapshots"
    )
    op.execute("DROP FUNCTION reject_copilot_citation_snapshot_mutation()")
    op.drop_table("copilot_citation_snapshots")
    op.drop_table("copilot_suggestions")
    op.drop_table("copilot_cases")
