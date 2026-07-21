from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.audit.models import AuditEvent
from fruit_agent.config import get_settings
from fruit_agent.db import SessionFactory, engine, get_session, tenant_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Membership, Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider
from fruit_agent.knowledge.models import KnowledgeType
from fruit_agent.knowledge.repository import KnowledgeRepository


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

        seed_session.add_all(
            [
                Membership(
                    tenant_id=tenant_a_id,
                    user_id=operator_id,
                    role=Role.operator.value,
                    valid_until=valid_until,
                ),
                Membership(
                    tenant_id=tenant_a_id,
                    user_id=owner_id,
                    role=Role.owner.value,
                    valid_until=valid_until,
                ),
                Membership(
                    tenant_id=tenant_b_id,
                    user_id=implementer_id,
                    role=Role.implementer.value,
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
async def test_session_exposes_current_role_permissions(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, _, _, session = knowledge_management_context
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/session")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(operator.user_id),
        "tenant_id": str(operator.tenant_id),
        "role": "operator",
        "permissions": [
            "approval:request",
            "copilot:use",
            "imports:write",
            "knowledge:read",
            "knowledge:write",
            "members:read",
        ],
    }
    await session.close()


class _RecordingEmbeddingProvider:
    model_name = "semantic-test"
    model_version = "2026-07"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, *([0.0] * 1535)]


@pytest.mark.asyncio
async def test_knowledge_mutations_emit_redacted_immutable_audits(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, owner, _, session = knowledge_management_context
    payload = _knowledge_payload(operator.user_id)
    payload["content"] = "Contact 13800138000 about storage."
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/knowledge/items",
                json=payload,
            )
            updated = await client.patch(
                f"/api/v1/knowledge/items/{created.json()['id']}",
                json={"content": "Ask contact wxid_knowledge123."},
            )
            app.dependency_overrides[get_principal] = lambda: owner
            reviewed = await client.post(
                f"/api/v1/knowledge/items/{created.json()['id']}/review",
                json={"review_status": "approved"},
            )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert updated.status_code == 200
    assert reviewed.status_code == 200
    async with tenant_session(session, operator.tenant_id):
        audits = list(
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.entity_id == UUID(created.json()["id"]))
                .order_by(AuditEvent.created_at)
            )
        )
    assert [event.action for event in audits] == [
        "knowledge.created",
        "knowledge.updated",
        "knowledge.reviewed",
    ]
    rendered = repr([(event.before, event.after) for event in audits])
    assert "13800138000" not in rendered
    assert "wxid_knowledge123" not in rendered
    await session.close()


@pytest.mark.asyncio
async def test_search_returns_only_current_tenant_approved_narrative_items(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, owner, other_tenant, session = knowledge_management_context
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
            app.dependency_overrides[get_principal] = lambda: owner
            await client.post(
                f"/api/v1/knowledge/items/{created.json()['id']}/review",
                json={"review_status": "approved"},
            )
            app.dependency_overrides[get_principal] = lambda: operator
            own = await client.get(
                "/api/v1/knowledge/items/search",
                params={"q": "How should Fuji apples be stored?", "limit": 5},
            )
            app.dependency_overrides[get_principal] = lambda: other_tenant
            other = await client.get(
                "/api/v1/knowledge/items/search",
                params={"q": "How should Fuji apples be stored?", "limit": 5},
            )
    finally:
        app.dependency_overrides.clear()
    assert own.status_code == 200
    assert [item["id"] for item in own.json()] == [created.json()["id"]]
    assert other.status_code == 200
    assert other.json() == []
    await session.close()


@pytest.mark.asyncio
async def test_production_rejects_deterministic_provider_with_503(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operator, _, _, session = knowledge_management_context
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    app.state.embedding_provider = DeterministicEmbeddingProvider()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/knowledge/items",
                json=_knowledge_payload(operator.user_id),
            )
    finally:
        app.dependency_overrides.clear()
        app.state.embedding_provider = DeterministicEmbeddingProvider()
        get_settings.cache_clear()

    assert response.status_code == 503
    assert (
        response.json()["error"]["message"]
        == "embedding provider is not configured"
    )
    await session.close()


@pytest.mark.asyncio
async def test_read_review_and_exact_sku_routes_do_not_require_provider(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, owner, _, session = knowledge_management_context
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator
    app.state.embedding_provider = DeterministicEmbeddingProvider()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/knowledge/items",
                json=_knowledge_payload(operator.user_id),
            )
            app.state.embedding_provider = None
            listed = await client.get("/api/v1/knowledge/items")
            exact = await client.get("/api/v1/knowledge/skus/UNKNOWN")
            app.dependency_overrides[get_principal] = lambda: owner
            reviewed = await client.post(
                f"/api/v1/knowledge/items/{created.json()['id']}/review",
                json={"review_status": "approved"},
            )
    finally:
        app.dependency_overrides.clear()
        app.state.embedding_provider = DeterministicEmbeddingProvider()

    assert created.status_code == 201
    assert listed.status_code == 200
    assert exact.status_code == 200
    assert exact.json()["status"] == "not_found"
    assert reviewed.status_code == 200
    await session.close()


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
async def test_knowledge_write_uses_injected_embedding_provider_and_persists_version(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, _, _, session = knowledge_management_context
    provider = _RecordingEmbeddingProvider()
    app.state.embedding_provider = provider
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
    finally:
        app.dependency_overrides.clear()
        app.state.embedding_provider = DeterministicEmbeddingProvider()

    assert created.status_code == 201
    assert provider.calls == ["Store Fuji apples in the refrigerator."]
    assert created.json()["embedding_model"] == provider.model_name
    assert created.json()["embedding_version"] == provider.model_version
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"source_name": None},
        {"responsible_user_id": None},
        {"valid_until": None},
    ],
)
async def test_knowledge_update_rejects_explicit_null_for_required_fields(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
    changes: dict[str, None],
) -> None:
    operator, _, _, session = knowledge_management_context
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
            response = await client.patch(
                f"/api/v1/knowledge/items/{created.json()['id']}",
                json=changes,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    await session.close()


@pytest.mark.asyncio
async def test_knowledge_responsible_user_must_be_active_member_of_tenant(
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
            payload = _knowledge_payload(tenant_b_implementer.user_id)
            rejected_create = await client.post("/api/v1/knowledge/items", json=payload)
            assert rejected_create.status_code == 422

            created = await client.post(
                "/api/v1/knowledge/items",
                json=_knowledge_payload(operator.user_id),
            )
            assert created.status_code == 201
            rejected_update = await client.patch(
                f"/api/v1/knowledge/items/{created.json()['id']}",
                json={"responsible_user_id": str(tenant_b_implementer.user_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert rejected_update.status_code == 422
    await session.close()


@pytest.mark.asyncio
async def test_cross_tenant_knowledge_list_is_empty_and_review_is_hidden(
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
            listed = await client.get("/api/v1/knowledge/items")
            hidden_review = await client.post(
                f"/api/v1/knowledge/items/{knowledge_id}/review",
                json={"review_status": "approved"},
            )
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert listed.json() == []
    assert hidden_review.status_code == 404
    await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"knowledge_type": "origin_story"},
        {"source_name": "Updated grower handbook"},
        {"responsible_user_id": "owner"},
        {"valid_until": "extended"},
    ],
)
async def test_approved_knowledge_editing_retrieval_or_provenance_resets_to_draft(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
    changes: dict[str, str],
) -> None:
    operator, owner, _, session = knowledge_management_context
    if changes.get("responsible_user_id") == "owner":
        changes = {"responsible_user_id": str(owner.user_id)}
    if changes.get("valid_until") == "extended":
        changes = {"valid_until": (datetime.now(UTC) + timedelta(days=14)).isoformat()}
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

            app.dependency_overrides[get_principal] = lambda: owner
            approved = await client.post(
                f"/api/v1/knowledge/items/{knowledge_id}/review",
                json={"review_status": "approved"},
            )
            assert approved.status_code == 200

            app.dependency_overrides[get_principal] = lambda: operator
            edited = await client.patch(
                f"/api/v1/knowledge/items/{knowledge_id}",
                json=changes,
            )
    finally:
        app.dependency_overrides.clear()

    assert edited.status_code == 200
    assert edited.json()["review_status"] == "draft"
    await session.close()


@pytest.mark.asyncio
async def test_extending_approved_knowledge_validity_makes_it_ineligible_until_reapproved(
    knowledge_management_context: tuple[
        TenantPrincipal, TenantPrincipal, TenantPrincipal, AsyncSession
    ],
) -> None:
    operator, owner, _, session = knowledge_management_context
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: operator
    content = "Store Fuji apples in the refrigerator."

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

            app.dependency_overrides[get_principal] = lambda: owner
            approved = await client.post(
                f"/api/v1/knowledge/items/{knowledge_id}/review",
                json={"review_status": "approved"},
            )
            assert approved.status_code == 200

            app.dependency_overrides[get_principal] = lambda: operator
            extended = await client.patch(
                f"/api/v1/knowledge/items/{knowledge_id}",
                json={"valid_until": (datetime.now(UTC) + timedelta(days=14)).isoformat()},
            )
            assert extended.status_code == 200

            async with tenant_session(session, operator.tenant_id):
                rows = await KnowledgeRepository(session).search_semantic(
                    tenant_id=operator.tenant_id,
                    query_embedding=DeterministicEmbeddingProvider().embed(content),
                    knowledge_types=[KnowledgeType.faq],
                    now=datetime.now(UTC),
                    limit=5,
                )
    finally:
        app.dependency_overrides.clear()

    assert extended.json()["review_status"] == "draft"
    assert rows == []
    await session.close()
