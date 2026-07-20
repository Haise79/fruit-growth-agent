from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from fruit_agent.identity.models import MembershipStatus, Role


class TenantPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    tenant_id: UUID
    role: Role


class SessionRead(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: Role
    permissions: list[str]


class MemberCreate(BaseModel):
    email: EmailStr
    role: Role


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    email: EmailStr
    role: Role
    status: MembershipStatus
