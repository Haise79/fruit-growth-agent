from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fruit_agent.common.models import Base, LifecycleAuditMixin, TenantOwnedMixin


class Role(StrEnum):
    owner = "owner"
    operator = "operator"
    support = "support"
    implementer = "implementer"


class MembershipStatus(StrEnum):
    active = "active"
    invited = "invited"
    suspended = "suspended"


class Tenant(LifecycleAuditMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class User(TenantOwnedMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_users_tenant_id_id"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)


class Membership(TenantOwnedMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "user_id"),
            ("users.tenant_id", "users.id"),
            ondelete="CASCADE",
            name="fk_memberships_tenant_user",
        ),
        UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MembershipStatus.active.value,
        server_default=MembershipStatus.active.value,
    )
