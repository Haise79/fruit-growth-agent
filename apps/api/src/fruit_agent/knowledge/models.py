from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fruit_agent.common.models import Base, TenantOwnedMixin

EMBEDDING_DIMENSION = 1536


class KnowledgeType(StrEnum):
    faq = "faq"
    talking_point = "talking_point"
    origin_story = "origin_story"
    product_fact = "product_fact"
    inventory_fact = "inventory_fact"
    price_fact = "price_fact"


class ReviewStatus(StrEnum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class ProductSKU(TenantOwnedMixin, Base):
    __tablename__ = "product_skus"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "sku_code",
            "source_id",
            name="uq_product_skus_tenant_code_source",
        ),
        CheckConstraint("inventory >= 0", name="ck_product_skus_inventory"),
        CheckConstraint("price >= 0", name="ck_product_skus_price"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sku_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    inventory: Mapped[int] = mapped_column(nullable=False)
    source_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    variety: Mapped[str | None] = mapped_column(String(200), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(300), nullable=True)
    orchard: Mapped[str | None] = mapped_column(String(300), nullable=True)
    taste: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ripeness: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specification: Mapped[str | None] = mapped_column(String(300), nullable=True)
    net_weight_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_regions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    shipping_eta: Mapped[str | None] = mapped_column(String(200), nullable=True)


class MerchantKnowledge(TenantOwnedMixin, Base):
    __tablename__ = "merchant_knowledge"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "responsible_user_id"),
            ("users.tenant_id", "users.id"),
            name="fk_merchant_knowledge_tenant_responsible",
        ),
        Index(
            "ix_merchant_knowledge_tenant_responsible_user",
            "tenant_id",
            "responsible_user_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    knowledge_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    review_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ReviewStatus.draft.value,
        server_default=ReviewStatus.draft.value,
        index=True,
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        default="legacy",
        server_default="legacy",
    )
    responsible_user_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="deterministic-sha256",
        server_default="deterministic-sha256",
    )
    embedding_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="1",
        server_default="1",
    )
