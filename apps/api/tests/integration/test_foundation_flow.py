from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.db import SessionFactory, engine, get_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.model_gateway.schemas import (
    AgentSuggestion,
    ModelProfile,
    ProviderResponse,
)
from fruit_agent.model_gateway.service import ProviderBinding


@pytest.fixture
async def foundation_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.mark.asyncio
async def test_foundation_flow(foundation_database: None) -> None:
    del foundation_database
    tenant_id = uuid4()
    owner_id = uuid4()
    future = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as seed:
        seed.add(Tenant(id=tenant_id, name="Flow Tenant", valid_until=future))
        await seed.flush()
        seed.add(
            User(
                id=owner_id,
                tenant_id=tenant_id,
                email="owner@flow.example",
                valid_until=future,
            )
        )
        await seed.commit()

    principal = TenantPrincipal(
        tenant_id=tenant_id,
        user_id=owner_id,
        role=Role.owner,
    )
    provider = AsyncMock()
    provider.complete.return_value = ProviderResponse(
        suggestion=AgentSuggestion(
            suggestion_text="推荐新鲜苹果",
            referenced_knowledge_ids=[],
            confidence_score=0.92,
            risk_level="low",
        ),
        input_tokens=20,
        output_tokens=10,
    )
    app.state.model_providers = [
        ProviderBinding(
            profile=ModelProfile(
                name="qwen-flow",
                estimated_cost_per_1k_tokens=0.001,
                fact_error_rate=0.01,
                high_risk_recall=0.98,
            ),
            provider=provider,
        )
    ]
    session: AsyncSession = SessionFactory()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            member = await client.post(
                "/api/v1/members",
                json={"email": "operator@flow.example", "role": "operator"},
            )
            imported = await client.post(
                "/api/v1/imports/products",
                files={
                    "file": (
                        "products.csv",
                        (
                            "sku_code,name,price,inventory,valid_until\n"
                            "A1,苹果,29.90,10,2030-01-01T00:00:00Z\n"
                        ).encode(),
                        "text/csv",
                    )
                },
            )
            suggestion = await client.post(
                "/api/v1/model-gateway/suggestions",
                json={"prompt": {"message": "推荐苹果"}},
            )
            approval = await client.post(
                "/api/v1/approvals",
                json={
                    "action": "change_inventory",
                    "payload": {"sku_code": "A1", "quantity": 8},
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []
        await session.close()

    assert member.status_code == 201
    assert member.json()["role"] == "operator"
    assert imported.status_code == 200
    assert imported.json()["failed_rows"] == 0
    assert suggestion.status_code == 200
    assert suggestion.json()["suggestion_text"] == "推荐新鲜苹果"
    assert approval.status_code == 201
    assert approval.json()["status"] == "pending"
    assert approval.json()["requires_approval"] is True
