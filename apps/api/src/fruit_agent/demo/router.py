from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.config import get_settings
from fruit_agent.db import get_session, tenant_session
from fruit_agent.demo.auth import DemoSessionRead, demo_enabled, issue_demo_token
from fruit_agent.demo.constants import DEMO_TENANT_ID, DEMO_USERS
from fruit_agent.identity.models import Membership, MembershipStatus, Role

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoSessionCreate(BaseModel):
    role: Role


@router.post(
    "/session",
    response_model=DemoSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_demo_session(
    body: DemoSessionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DemoSessionRead:
    settings = get_settings()
    if not demo_enabled(settings):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user_id = DEMO_USERS[body.role]
    async with tenant_session(session, DEMO_TENANT_ID):
        membership = await session.scalar(
            select(Membership).where(
                Membership.tenant_id == DEMO_TENANT_ID,
                Membership.user_id == user_id,
                Membership.role == body.role.value,
                Membership.status == MembershipStatus.active.value,
            )
        )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="demo data is not seeded",
        )
    return issue_demo_token(body.role, settings)
