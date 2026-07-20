"""Add embedding version metadata and final safety invariants.

Revision ID: 0008_final_safety_invariants
Revises: 0007_copilot_outcome_events
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_final_safety_invariants"
down_revision: str | None = "0007_copilot_outcome_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "merchant_knowledge",
        sa.Column(
            "embedding_model",
            sa.String(length=200),
            nullable=False,
            server_default="deterministic-sha256",
        ),
    )
    op.add_column(
        "merchant_knowledge",
        sa.Column(
            "embedding_version",
            sa.String(length=100),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_foreign_key(
        "fk_merchant_knowledge_tenant_responsible",
        "merchant_knowledge",
        "users",
        ["tenant_id", "responsible_user_id"],
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_merchant_knowledge_tenant_responsible_user",
        "merchant_knowledge",
        ["tenant_id", "responsible_user_id"],
    )
    op.create_check_constraint(
        "ck_copilot_cases_stage",
        "copilot_cases",
        "stage IN ('presale', 'aftersale', 'unknown')",
    )
    op.create_check_constraint(
        "ck_copilot_cases_intent",
        "copilot_cases",
        "intent IN ('product_info', 'recommendation', 'gift', "
        "'delivery', 'storage', 'damage', 'refund', 'complaint', "
        "'health_safety', 'other')",
    )
    op.create_check_constraint(
        "ck_copilot_cases_risk",
        "copilot_cases",
        "risk IN ('low', 'medium', 'high', 'critical')",
    )
    op.create_check_constraint(
        "ck_copilot_cases_status",
        "copilot_cases",
        "status IN ('suggestions_ready', 'handoff_required', "
        "'degraded', 'closed')",
    )
    op.create_check_constraint(
        "ck_copilot_citations_type",
        "copilot_citation_snapshots",
        "citation_type IN ('sku', 'knowledge')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_copilot_citations_type",
        "copilot_citation_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_copilot_cases_status",
        "copilot_cases",
        type_="check",
    )
    op.drop_constraint(
        "ck_copilot_cases_risk",
        "copilot_cases",
        type_="check",
    )
    op.drop_constraint(
        "ck_copilot_cases_intent",
        "copilot_cases",
        type_="check",
    )
    op.drop_constraint(
        "ck_copilot_cases_stage",
        "copilot_cases",
        type_="check",
    )
    op.drop_index(
        "ix_merchant_knowledge_tenant_responsible_user",
        table_name="merchant_knowledge",
    )
    op.drop_constraint(
        "fk_merchant_knowledge_tenant_responsible",
        "merchant_knowledge",
        type_="foreignkey",
    )
    op.drop_column("merchant_knowledge", "embedding_version")
    op.drop_column("merchant_knowledge", "embedding_model")
