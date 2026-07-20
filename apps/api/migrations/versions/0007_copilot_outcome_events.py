"""Create immutable, tenant-scoped copilot outcome events.

Revision ID: 0007_copilot_outcome_events
Revises: 0006_copilot_cases
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_copilot_outcome_events"
down_revision: str | None = "0006_copilot_cases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "copilot_outcome_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("suggestion_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.CheckConstraint(
            "event_type IN ('suggestion_adopted', 'suggestion_rejected', "
            "'payment', 'refund', 'complaint', 'case_closed')",
            name="ck_copilot_outcomes_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_copilot_outcomes_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["copilot_cases.tenant_id", "copilot_cases.id"],
            name="fk_copilot_outcomes_tenant_case",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "suggestion_id"],
            ["copilot_suggestions.tenant_id", "copilot_suggestions.id"],
            name="fk_copilot_outcomes_tenant_suggestion",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "idempotency_key",
            name="uq_copilot_outcomes_tenant_case_idempotency",
        ),
    )
    op.create_index("ix_copilot_outcomes_tenant_id", "copilot_outcome_events", ["tenant_id"])
    op.create_index("ix_copilot_outcomes_case_id", "copilot_outcome_events", ["case_id"])
    op.create_index("ix_copilot_outcomes_suggestion_id", "copilot_outcome_events", ["suggestion_id"])
    op.execute("ALTER TABLE copilot_outcome_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE copilot_outcome_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY copilot_outcome_events_tenant_isolation ON copilot_outcome_events
        USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_copilot_outcome_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'copilot outcome events are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER copilot_outcome_events_immutable
        BEFORE UPDATE OR DELETE ON copilot_outcome_events
        FOR EACH ROW
        EXECUTE FUNCTION reject_copilot_outcome_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER copilot_outcome_events_immutable ON copilot_outcome_events")
    op.execute("DROP FUNCTION reject_copilot_outcome_event_mutation()")
    op.drop_table("copilot_outcome_events")
