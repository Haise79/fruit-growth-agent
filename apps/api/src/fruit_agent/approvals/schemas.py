from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from fruit_agent.approvals.models import ApprovalStatus, RiskyAction


class ApprovalCreate(BaseModel):
    action: RiskyAction
    payload: dict[str, object]


class ApprovalDecision(BaseModel):
    decision: Literal[ApprovalStatus.approved, ApprovalStatus.rejected]


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    requested_by: UUID
    action: RiskyAction
    payload: dict[str, object]
    requires_approval: bool
    status: ApprovalStatus
    decided_by: UUID | None
    decided_at: datetime | None
