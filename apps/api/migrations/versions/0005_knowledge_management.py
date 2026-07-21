"""Add SKU narrative facts and managed merchant knowledge metadata.

Revision ID: 0005_knowledge_management
Revises: 0004_knowledge
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_knowledge_management"
down_revision: str | None = "0004_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("product_skus", sa.Column("variety", sa.String(length=200), nullable=True))
    op.add_column("product_skus", sa.Column("origin", sa.String(length=300), nullable=True))
    op.add_column("product_skus", sa.Column("orchard", sa.String(length=300), nullable=True))
    op.add_column("product_skus", sa.Column("taste", sa.String(length=300), nullable=True))
    op.add_column("product_skus", sa.Column("ripeness", sa.String(length=200), nullable=True))
    op.add_column("product_skus", sa.Column("specification", sa.String(length=300), nullable=True))
    op.add_column("product_skus", sa.Column("net_weight_grams", sa.Integer(), nullable=True))
    op.add_column(
        "product_skus",
        sa.Column("sales_regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("product_skus", sa.Column("shipping_eta", sa.String(length=200), nullable=True))

    op.add_column(
        "merchant_knowledge",
        sa.Column(
            "source_name",
            sa.String(length=300),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.alter_column("merchant_knowledge", "source_name", server_default=None)
    op.add_column(
        "merchant_knowledge",
        sa.Column("responsible_user_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_merchant_knowledge_responsible_user_id",
        "merchant_knowledge",
        ["responsible_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_knowledge_responsible_user_id", table_name="merchant_knowledge")
    op.drop_column("merchant_knowledge", "responsible_user_id")
    op.drop_column("merchant_knowledge", "source_name")
    op.drop_column("product_skus", "shipping_eta")
    op.drop_column("product_skus", "sales_regions")
    op.drop_column("product_skus", "net_weight_grams")
    op.drop_column("product_skus", "specification")
    op.drop_column("product_skus", "ripeness")
    op.drop_column("product_skus", "taste")
    op.drop_column("product_skus", "orchard")
    op.drop_column("product_skus", "origin")
    op.drop_column("product_skus", "variety")
