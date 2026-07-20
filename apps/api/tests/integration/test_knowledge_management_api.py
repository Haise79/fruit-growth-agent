from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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


@pytest.fixture
async def knowledge_management_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
async def knowledge_management_context(
    knowledge_management_database: None,
) -> tuple[TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession]:
    del knowledge_management_database
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    operator_id = uuid4()
    owner_id = uuid4()
    implementer_id = uuid4()
    valid_until = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as seed_session:
        seed_session.add_all(
            [
                Tenant(id=tenant_a_id, name="Tenant A", valid_until=valid_until),
                Tenant(id=tenant_b_id, name="Tenant B", valid_until=valid_until),
                User(
                    id=operator_id,
                    tenant_id=tenant_a_id,
                    email="operator@example.com",
                    valid_until=valid_until,
                ),
                User(
                    id=owner_id,
                    tenant_id=tenant_a_id,
                    email="owner@example.com",
                    valid_until=valid_until,
                ),
                User(
                    id=implementer_id,
                    tenant_id=tenant_b_id,
                    email="implementer@example.com",
                    valid_until=valid_until,
                ),
            ]
        )
        await seed_session.commit()

    return (
        TenantPrincipal(
            tenant_id=tenant_a_id,
            user_id=operator_id,
            role=Role.operator,
        ),
        TenantPrincipal(tenant_id=tenant_a_id, user_id=owner_id, role=Role.owner),
        TenantPrincipal(
            tenant_id=tenant_b_id,
            user_id=implementer_id,
            role=Role.implementer,
        ),
        SessionFactory(),
    )


def _knowledge_payload(responsible_user_id: UUID) -> dict[str, str]:
    return {
        "knowledge_type": "faq",
        "content": "Store Fuji apples in the refrigerator.",
        "source_name": "Grower handbook",
        "responsible_user_id": str(responsible_user_id),
        "valid_until": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    }


@pytest.mark.asyncio
async def test_knowledge_create_list_edit_and_review_permissions(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, owner, _, session = knowledge_management_context
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/knowledge/items",
                json=_knowledge_payload(operator.user_id),
            )
            assert created.status_code == 201
            item = created.json()
            assert item["review_status"] == "draft"
            assert item["source_name"] == "Grower handbook"
            assert item["responsible_user_id"] == str(operator.user_id)

            listed = await client.get("/api/v1/knowledge/items")
            assert listed.status_code == 200
            assert [row["id"] for row in listed.json()] == [item["id"]]

            denied_review = await client.post(
                f"/api/v1/knowledge/items/{item['id']}/review",
                json={"review_status": "approved"},
            )
            assert denied_review.status_code == 403

            app.dependency_overrides[get_principal] = lambda: owner
            approved = await client.post(
                f"/api/v1/knowledge/items/{item['id']}/review",
                json={"review_status": "approved"},
            )
            assert approved.status_code == 200
            assert approved.json()["review_status"] == "approved"

            app.dependency_overrides[get_principal] = lambda: operator
            edited = await client.patch(
                f"/api/v1/knowledge/items/{item['id']}",
                json={"content": "Keep Fuji apples cold and dry."},
            )
    finally:
        app.dependency_overrides.clear()

    assert edited.status_code == 200
    assert edited.json()["content"] == "Keep Fuji apples cold and dry."
    assert edited.json()["review_status"] == "draft"
    await session.close()


@pytest.mark.asyncio
async def test_knowledge_cross_tenant_item_is_hidden(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, _, tenant_b_implementer, session = knowledge_management_context
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/knowledge/items",
                json=_knowledge_payload(operator.user_id),
            )
            assert created.status_code == 201
            knowledge_id = created.json()["id"]

            app.dependency_overrides[get_principal] = lambda: tenant_b_implementer
            hidden = await client.patch(
                f"/api/v1/knowledge/items/{knowledge_id}",
                json={"content": "Cross-tenant overwrite"},
            )
    finally:
        app.dependency_overrides.clear()

    assert hidden.status_code == 404
    await session.close()
