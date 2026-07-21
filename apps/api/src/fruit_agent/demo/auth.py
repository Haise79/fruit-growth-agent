from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from pydantic import BaseModel

from fruit_agent.config import Settings
from fruit_agent.demo.constants import DEMO_TENANT_ID, DEMO_USERS
from fruit_agent.identity.models import Role

DEMO_SESSION_DURATION = timedelta(minutes=30)


class DemoSessionRead(BaseModel):
    access_token: str
    expires_at: datetime
    role: Role


def demo_enabled(settings: Settings) -> bool:
    return settings.environment == "development" and settings.demo_mode


def jwt_verification_key(settings: Settings) -> str:
    if settings.jwt_public_key:
        return settings.jwt_public_key
    if demo_enabled(settings):
        return Path(settings.demo_public_key_path).read_text(encoding="utf-8")
    return ""


def issue_demo_token(
    role: Role,
    settings: Settings,
    now: datetime | None = None,
) -> DemoSessionRead:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + DEMO_SESSION_DURATION
    private_key = Path(settings.demo_private_key_path).read_text(encoding="utf-8")
    token = jwt.encode(
        {
            "sub": str(DEMO_USERS[role]),
            "tenant_id": str(DEMO_TENANT_ID),
            "aud": settings.jwt_audience,
            "iat": issued_at,
            "exp": expires_at,
        },
        private_key,
        algorithm="RS256",
    )
    return DemoSessionRead(
        access_token=token,
        expires_at=expires_at,
        role=role,
    )
