from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import CheckConstraint, Numeric, String, UniqueConstraint
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


class MerchantKnowledge(TenantOwnedMixin, Base):
    __tablename__ = "merchant_knowledge"

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
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=False,
    )
