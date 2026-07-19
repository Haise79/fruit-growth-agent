"""Create exact SKU facts and vector merchant knowledge.

Revision ID: 0004_knowledge
Revises: 0003_approval_requests
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_knowledge"
down_revision: str | None = "0003_approval_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _lifecycle_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "audit_log",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    ]


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def upgrade() -> None:
    op.create_table(
        "product_skus",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sku_code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("inventory", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        *_lifecycle_columns(),
        sa.CheckConstraint("inventory >= 0", name="ck_product_skus_inventory"),
        sa.CheckConstraint("price >= 0", name="ck_product_skus_price"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_product_skus_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "sku_code",
            "source_id",
            name="uq_product_skus_tenant_code_source",
        ),
    )
    op.create_index("ix_product_skus_tenant_id", "product_skus", ["tenant_id"])
    op.create_index("ix_product_skus_sku_code", "product_skus", ["sku_code"])
    op.create_index("ix_product_skus_source_id", "product_skus", ["source_id"])
    _enable_rls("product_skus")

    op.create_table(
        "merchant_knowledge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_type", sa.String(length=64), nullable=False),
        sa.Column(
            "review_status",
            sa.String(length=32),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.Vector(dim=1536),
            nullable=False,
        ),
        *_lifecycle_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_merchant_knowledge_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_merchant_knowledge_tenant_id",
        "merchant_knowledge",
        ["tenant_id"],
    )
    op.create_index(
        "ix_merchant_knowledge_knowledge_type",
        "merchant_knowledge",
        ["knowledge_type"],
    )
    op.create_index(
        "ix_merchant_knowledge_review_status",
        "merchant_knowledge",
        ["review_status"],
    )
    op.create_index(
        "ix_merchant_knowledge_source_id",
        "merchant_knowledge",
        ["source_id"],
    )
    _enable_rls("merchant_knowledge")


def downgrade() -> None:
    op.drop_table("merchant_knowledge")
    op.drop_table("product_skus")
