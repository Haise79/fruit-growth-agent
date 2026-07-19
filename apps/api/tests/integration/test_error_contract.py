from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.db import get_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Role
from fruit_agent.identity.schemas import TenantPrincipal


@pytest.mark.asyncio
async def test_validation_error_has_stable_contract() -> None:
    principal = TenantPrincipal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        role=Role.operator,
    )
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_session] = lambda: AsyncMock(
        spec=AsyncSession
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/imports/products")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert set(response.json()["error"]) == {
        "code",
        "message",
        "request_id",
        "details",
    }
    assert response.json()["error"]["request_id"] == response.headers[
        "X-Request-ID"
    ]
