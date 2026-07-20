from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.db import SessionFactory, engine, get_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Membership, Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider
from fruit_agent.knowledge.models import (
    EMBEDDING_DIMENSION,
    KnowledgeType,
    MerchantKnowledge,
    ProductSKU,
    ReviewStatus,
)
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.model_gateway.schemas import (
    CopilotAgentOutput,
    CopilotAgentSuggestion,
    CopilotProviderResponse,
    ModelProfile,
)
from fruit_agent.model_gateway.service import ProviderBinding, ProviderUnavailableError


class SemanticTestEmbeddingProvider:
    model_name = "semantic-test"
    model_version = "1"

    def embed(self, text: str) -> list[float]:
        del text
        return [1.0, *([0.0] * (EMBEDDING_DIMENSION - 1))]


class FailingEmbeddingProvider:
    model_name = "failing-test"
    model_version = "1"

    def embed(self, text: str) -> list[float]:
        del text
        raise RuntimeError("embedding backend unavailable")


@pytest.fixture
async def copilot_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
async def copilot_context(
    copilot_database: None,
) -> tuple[TenantPrincipal, TenantPrincipal, AsyncSession]:
    del copilot_database
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    support_a_id = uuid4()
    support_b_id = uuid4()
    future = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as seed:
        seed.add_all(
            [
                Tenant(id=tenant_a_id, name="Tenant A", valid_until=future),
                Tenant(id=tenant_b_id, name="Tenant B", valid_until=future),
                User(
                    id=support_a_id,
                    tenant_id=tenant_a_id,
                    email="support-a@example.com",
                    valid_until=future,
                ),
                User(
                    id=support_b_id,
                    tenant_id=tenant_b_id,
                    email="support-b@example.com",
                    valid_until=future,
                ),
            ]
        )
        await seed.flush()
        seed.add_all(
            [
                Membership(
                    tenant_id=tenant_a_id,
                    user_id=support_a_id,
                    role=Role.support.value,
                    valid_until=future,
                ),
                Membership(
                    tenant_id=tenant_b_id,
                    user_id=support_b_id,
                    role=Role.support.value,
                    valid_until=future,
                ),
            ]
        )
        await seed.commit()
    return (
        TenantPrincipal(
            tenant_id=tenant_a_id,
            user_id=support_a_id,
            role=Role.support,
        ),
        TenantPrincipal(
            tenant_id=tenant_b_id,
            user_id=support_b_id,
            role=Role.support,
        ),
        SessionFactory(),
    )


def _provider_response(
    *,
    risk: str = "low",
    recommended_sku_code: str | None = "APPLE-001",
    referenced_knowledge_ids: list[UUID] | None = None,
) -> CopilotProviderResponse:
    return CopilotProviderResponse(
        output=CopilotAgentOutput(
            stage="presale",
            intent="recommendation",
            risk_level=risk,  # type: ignore[arg-type]
            suggestions=[
                CopilotAgentSuggestion(
                    suggestion_text="推荐新鲜红富士，脆甜多汁。",
                    referenced_knowledge_ids=referenced_knowledge_ids or [],
                    recommended_sku_code=recommended_sku_code,
                    confidence_score=0.93,
                    risk_tip="请确认配送地区和到货时间。",
                )
            ],
        ),
        input_tokens=30,
        output_tokens=20,
    )


def _binding(provider: AsyncMock) -> ProviderBinding:
    return ProviderBinding(
        profile=ModelProfile(
            name="copilot-test",
            estimated_cost_per_1k_tokens=0.001,
            fact_error_rate=0.01,
            high_risk_recall=0.98,
        ),
        provider=provider,
    )


def _provider_response_with_facts(
    *,
    suggestion_text: str,
    fact_claims: dict[str, object],
) -> CopilotProviderResponse:
    return CopilotProviderResponse(
        output=CopilotAgentOutput(
            stage="presale",
            intent="recommendation",
            risk_level="low",
            suggestions=[
                CopilotAgentSuggestion.model_validate(
                    {
                        "suggestion_text": suggestion_text,
                        "referenced_knowledge_ids": [],
                        "recommended_sku_code": "APPLE-001",
                        "confidence_score": 0.93,
                        "risk_tip": "Confirm current shipping availability.",
                        "fact_claims": fact_claims,
                    }
                )
            ],
        ),
        input_tokens=30,
        output_tokens=20,
    )


async def _seed_sku(
    principal: TenantPrincipal,
    *,
    price: str = "29.90",
    valid_until: datetime | None = None,
) -> None:
    async with SessionFactory() as seed:
        seed.add(
            ProductSKU(
                tenant_id=principal.tenant_id,
                sku_code="APPLE-001",
                name="红富士苹果",
                price=Decimal(price),
                inventory=100,
                source_id=uuid4(),
                origin="山东烟台",
                variety="红富士",
                orchard="示范果园",
                taste="脆甜",
                ripeness="即食",
                specification="12 枚礼盒",
                net_weight_grams=2500,
                sales_regions=["华东", "华南"],
                valid_until=valid_until
                or datetime.now(UTC) + timedelta(days=7),
            )
        )
        await seed.commit()


async def _seed_knowledge(
    principal: TenantPrincipal,
    *,
    status: ReviewStatus = ReviewStatus.approved,
    valid_until: datetime | None = None,
    content: str = "红富士苹果冷藏可保持更好的脆度。",
) -> UUID:
    knowledge_id = uuid4()
    async with SessionFactory() as seed:
        seed.add(
            MerchantKnowledge(
                id=knowledge_id,
                tenant_id=principal.tenant_id,
                knowledge_type=KnowledgeType.faq.value,
                review_status=status.value,
                content=content,
                source_id=uuid4(),
                source_name="果园客服手册",
                responsible_user_id=principal.user_id,
                embedding=DeterministicEmbeddingProvider().embed(content),
                valid_until=valid_until
                or datetime.now(UTC) + timedelta(days=7),
            )
        )
        await seed.commit()
    return knowledge_id


@pytest.mark.asyncio
async def test_semantic_retrieval_finds_relevant_item_beyond_five_candidates(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    relevant_id = uuid4()
    future = datetime.now(UTC) + timedelta(days=7)
    irrelevant_vector = [0.0, 1.0, *([0.0] * (EMBEDDING_DIMENSION - 2))]
    relevant_vector = [1.0, *([0.0] * (EMBEDDING_DIMENSION - 1))]
    async with SessionFactory() as seed:
        seed.add_all(
            [
                MerchantKnowledge(
                    tenant_id=tenant_a.tenant_id,
                    knowledge_type=KnowledgeType.faq.value,
                    review_status=ReviewStatus.approved.value,
                    content=f"Unrelated policy number {index}.",
                    source_id=uuid4(),
                    source_name=f"Source {index}",
                    responsible_user_id=tenant_a.user_id,
                    embedding=irrelevant_vector,
                    embedding_model="semantic-test",
                    embedding_version="1",
                    valid_until=future,
                )
                for index in range(6)
            ]
        )
        seed.add(
            MerchantKnowledge(
                id=relevant_id,
                tenant_id=tenant_a.tenant_id,
                knowledge_type=KnowledgeType.faq.value,
                review_status=ReviewStatus.approved.value,
                content="Apples should be stored in the refrigerator.",
                source_id=uuid4(),
                source_name="Storage guide",
                responsible_user_id=tenant_a.user_id,
                embedding=relevant_vector,
                embedding_model="semantic-test",
                embedding_version="1",
                valid_until=future,
            )
        )
        await seed.commit()

    provider = AsyncMock()
    provider.complete.return_value = _provider_response(
        referenced_knowledge_ids=[relevant_id]
    )
    app.state.model_providers = [_binding(provider)]
    app.state.embedding_provider = SemanticTestEmbeddingProvider()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "How should apples be stored?",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []
        app.state.embedding_provider = DeterministicEmbeddingProvider()

    assert response.status_code == 201
    assert response.json()["status"] == "suggestions_ready"
    prompt = provider.complete.await_args.args[0]
    assert prompt["sku_evidence"][0] | {
        "variety": "红富士",
        "orchard": "示范果园",
        "ripeness": "即食",
        "specification": "12 枚礼盒",
        "net_weight_grams": 2500,
        "sales_regions": ["华东", "华南"],
    } == prompt["sku_evidence"][0]
    assert [item["id"] for item in prompt["knowledge_evidence"]] == [
        str(relevant_id)
    ]
    await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["embed", "search"])
async def test_embedding_failures_persist_safe_handoff_instead_of_500(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    if failure_stage == "embed":
        app.state.embedding_provider = FailingEmbeddingProvider()
    else:
        app.state.embedding_provider = SemanticTestEmbeddingProvider()
        monkeypatch.setattr(
            KnowledgeRepository,
            "search_semantic",
            AsyncMock(side_effect=RuntimeError("vector search unavailable")),
        )
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "Please recommend this apple.",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
            history = await client.get("/api/v1/copilot/cases")
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []
        app.state.embedding_provider = DeterministicEmbeddingProvider()

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert "embedding_provider_error" in response.json()["risk_reasons"]
    assert history.json()[0]["id"] == response.json()["id"]
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
async def test_fresh_exact_evidence_creates_redacted_suggestion_with_snapshot(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response(risk="medium")
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": (
                        "寄到上海市浦东新区世纪大道100号，"
                        "座机021-58881234，银行卡6222021234567890123，"
                        "护照E12345678，手机13800138000，"
                        "邮箱buyer@example.com，身份证310101199001011234，"
                        "想买红富士，请推荐"
                    ),
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    body = response.json()
    for sensitive in (
        "上海市浦东新区世纪大道100号",
        "021-58881234",
        "6222021234567890123",
        "E12345678",
        "13800138000",
        "buyer@example.com",
        "310101199001011234",
    ):
        assert sensitive not in body["message"]
    assert body["risk"] == "medium"
    assert body["status"] == "suggestions_ready"
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["original_text"] == "推荐新鲜红富士，脆甜多汁。"
    assert suggestion["edited_text"] is None
    assert suggestion["recommended_sku_code"] == "APPLE-001"
    assert suggestion["rank"] == 1
    assert suggestion["degraded"] is False
    assert suggestion["citations"][0]["citation_type"] == "sku"
    assert suggestion["citations"][0]["snapshot"]["sku_code"] == "APPLE-001"
    sent_prompt = provider.complete.await_args.args[0]
    for sensitive in (
        "上海市浦东新区世纪大道100号",
        "021-58881234",
        "6222021234567890123",
        "E12345678",
        "13800138000",
        "buyer@example.com",
        "310101199001011234",
    ):
        assert sensitive not in repr(sent_prompt)
    await session.close()


@pytest.mark.asyncio
async def test_deterministic_handoff_persists_redaction_and_skips_provider(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "电话 13800138000，我吃完过敏了",
                    "selected_sku_codes": [],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["risk"] == "critical"
    assert response.json()["suggestions"] == []
    assert "13800138000" not in repr(response.json())
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_message",
    [
        "Ship to 123 Main Street, Springfield, IL 62704",
        "WeChat ID: wxid_alice123",
        "customer_name Alice Zhang",
        "My QQ is 123456789",
        "Alipay handle is alice.pay",
    ],
)
async def test_pii_bypasses_are_redacted_before_persistence_and_provider_invocation(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
    raw_message: str,
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": raw_message,
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
            history = await client.get("/api/v1/copilot/cases")
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "suggestions_ready"
    assert raw_message not in repr(response.json())
    assert raw_message not in repr(history.json())
    assert raw_message not in repr(provider.complete.await_args.args[0])
    await session.close()


@pytest.mark.asyncio
async def test_unisolatable_residual_pii_uses_placeholder_and_skips_provider(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a
    raw_message = "Please contact wxid_alice123 about this apple."

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": raw_message,
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
            history = await client.get("/api/v1/copilot/cases")
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["message"] == "[REDACTED: PII]"
    assert "pii_detected" in response.json()["risk_reasons"]
    assert raw_message not in repr(response.json())
    assert raw_message not in repr(history.json())
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "The customer stopped breathing after consuming the apple.",
        "She collapsed after eating the apple.",
        "He is unresponsive and couldn't breathe after consuming the fruit.",
    ],
)
async def test_severe_deterministic_risk_skips_low_risk_provider(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
    message: str,
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response(risk="low")
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": message,
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["risk"] == "critical"
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
async def test_delivery_status_phrase_is_not_redacted_as_an_address_and_hands_off(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "快递送到后苹果发霉了",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["message"] == "快递送到后苹果发霉了"
    assert response.json()["risk"] == "critical"
    assert response.json()["status"] == "handoff_required"
    assert "food_safety" in response.json()["risk_reasons"]
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
async def test_raw_and_redacted_safety_merge_without_persisting_or_sending_raw_text(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a
    raw_message = "地址：苹果发霉了"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": raw_message,
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
            history = await client.get("/api/v1/copilot/cases")
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["message"] == "地址：[REDACTED]"
    assert raw_message not in repr(response.json())
    assert history.json()[0]["message"] == "地址：[REDACTED]"
    assert raw_message not in repr(history.json())
    assert response.json()["risk"] == "critical"
    assert response.json()["status"] == "handoff_required"
    assert "food_safety" in response.json()["risk_reasons"]
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence_state", ["missing", "expired", "conflict"])
async def test_missing_expired_or_conflicting_sku_evidence_hands_off(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
    evidence_state: str,
) -> None:
    tenant_a, _, session = copilot_context
    if evidence_state == "expired":
        await _seed_sku(
            tenant_a,
            valid_until=datetime.now(UTC) - timedelta(seconds=1),
        )
    elif evidence_state == "conflict":
        await _seed_sku(tenant_a, price="29.90")
        await _seed_sku(tenant_a, price="39.90")
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "请推荐这款苹果",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
async def test_model_high_risk_output_is_discarded_and_handed_off(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response(risk="high")
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "请推荐这款苹果",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["risk"] == "high"
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("citation_state", ["unknown", "unapproved", "expired"])
async def test_invalid_narrative_citation_hands_off(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
    citation_state: str,
) -> None:
    tenant_a, tenant_b, session = copilot_context
    if citation_state == "unknown":
        citation_id = await _seed_knowledge(tenant_b)
    elif citation_state == "unapproved":
        citation_id = await _seed_knowledge(
            tenant_a,
            status=ReviewStatus.draft,
        )
    else:
        citation_id = await _seed_knowledge(
            tenant_a,
            valid_until=datetime.now(UTC) - timedelta(seconds=1),
        )
    provider = AsyncMock()
    provider.complete.return_value = _provider_response(
        recommended_sku_code=None,
        referenced_knowledge_ids=[citation_id],
    )
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "苹果怎么冷藏保存？",
                    "selected_sku_codes": [],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    await session.close()


@pytest.mark.asyncio
async def test_recommended_sku_outside_fresh_context_hands_off(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response(
        recommended_sku_code="APPLE-999"
    )
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "请推荐这款苹果",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    await session.close()


@pytest.mark.asyncio
async def test_knowledge_only_suggestion_without_fresh_sku_hands_off(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    knowledge_id = await _seed_knowledge(
        tenant_a,
        content="Apples should be refrigerated to keep fresh.",
    )
    provider = AsyncMock()
    provider.complete.return_value = _provider_response(
        recommended_sku_code=None,
        referenced_knowledge_ids=[knowledge_id],
    )
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "How should I store apples?",
                    "selected_sku_codes": [],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    assert "invalid_model_evidence" in response.json()["risk_reasons"]
    await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suggestion_text", "fact_claims"),
    [
        ("Price: CNY 39.90.", {}),
        ("Origin: California.", {}),
        ("Inventory: 7 units.", {}),
        ("Net weight: 3 kg.", {}),
        ("Only ¥39.90.", {}),
        ("今天只要39.90元。", {}),
        ("These apples come from California.", {}),
        ("这些苹果来自 California。", {}),
        ("Only 7 in stock.", {}),
        ("This is a 3 kg pack.", {}),
        ("Price: CNY 29.90, but the final price is CNY 39.90.", {}),
        ("Only ¥29.90.", {}),
        ("The price is around thirty yuan.", {"price": "29.90", "currency": "CNY"}),
        ("Recommended at the current price.", {"price": "39.90", "currency": "CNY"}),
        ("Recommended from the listed orchard.", {"origin": "California"}),
        ("Recommended while stock lasts.", {"inventory": 7}),
        ("Recommended in this pack size.", {"net_weight_grams": 3000}),
    ],
)
async def test_contradictory_sku_facts_discard_the_whole_generation(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
    suggestion_text: str,
    fact_claims: dict[str, object],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response_with_facts(
        suggestion_text=suggestion_text,
        fact_claims=fact_claims,
    )
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "Please recommend this apple.",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    assert "invalid_model_evidence" in response.json()["risk_reasons"]
    await session.close()


@pytest.mark.asyncio
async def test_matching_prose_and_structured_facts_are_accepted(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response_with_facts(
        suggestion_text=(
            "Only ¥29.90, with 100 in stock, come from 山东烟台, in a 2.5 kg pack."
        ),
        fact_claims={
            "price": "29.90",
            "currency": "CNY",
            "inventory": 100,
            "origin": "山东烟台",
            "net_weight_grams": 2500,
        },
    )
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "Please recommend this apple.",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "suggestions_ready"
    await session.close()


@pytest.mark.asyncio
async def test_provider_unavailable_fails_closed_without_draft(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.side_effect = ProviderUnavailableError("offline")
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "请推荐这款苹果",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    await session.close()


@pytest.mark.asyncio
async def test_unexpected_provider_error_persists_handoff_case(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.side_effect = RuntimeError("unexpected SDK failure")
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "请推荐这款苹果",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    await session.close()


@pytest.mark.asyncio
async def test_unrelated_narrative_is_not_accepted_as_customer_evidence(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, _, session = copilot_context
    unrelated_id = await _seed_knowledge(
        tenant_a,
        content="苹果客服团队每周一更新排班和值班负责人。",
    )
    provider = AsyncMock()
    provider.complete.return_value = _provider_response(
        recommended_sku_code=None,
        referenced_knowledge_ids=[unrelated_id],
    )
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "苹果应该怎么冷藏保存？",
                    "selected_sku_codes": [],
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert response.status_code == 201
    assert response.json()["status"] == "handoff_required"
    assert response.json()["suggestions"] == []
    provider.complete.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
async def test_history_detail_and_edit_hide_cross_tenant_case_and_redact_edit(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    tenant_a, tenant_b, session = copilot_context
    await _seed_sku(tenant_a)
    provider = AsyncMock()
    provider.complete.return_value = _provider_response()
    app.state.model_providers = [_binding(provider)]
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: tenant_a

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/copilot/cases",
                json={
                    "message": "请推荐这款苹果",
                    "selected_sku_codes": ["APPLE-001"],
                },
            )
            assert created.status_code == 201
            case_id = created.json()["id"]
            suggestion_id = created.json()["suggestions"][0]["id"]

            own_history = await client.get("/api/v1/copilot/cases")
            own_detail = await client.get(f"/api/v1/copilot/cases/{case_id}")
            own_edit = await client.patch(
                f"/api/v1/copilot/cases/{case_id}/suggestions/{suggestion_id}",
                json={"edited_text": "请联系 13900139000，我帮您确认。"},
            )

            app.dependency_overrides[get_principal] = lambda: tenant_b
            other_history = await client.get("/api/v1/copilot/cases")
            other_detail = await client.get(f"/api/v1/copilot/cases/{case_id}")
            other_edit = await client.patch(
                f"/api/v1/copilot/cases/{case_id}/suggestions/{suggestion_id}",
                json={"edited_text": "越权编辑"},
            )
    finally:
        app.dependency_overrides.clear()
        app.state.model_providers = []

    assert own_history.status_code == 200
    assert [item["id"] for item in own_history.json()] == [case_id]
    assert own_detail.status_code == 200
    assert own_edit.status_code == 200
    assert own_edit.json()["edited_text"] == "请联系 [REDACTED]，我帮您确认。"
    assert other_history.status_code == 200
    assert other_history.json() == []
    assert other_detail.status_code == 404
    assert other_edit.status_code == 404
    await session.close()


@pytest.mark.asyncio
async def test_immutable_citation_parent_foreign_keys_are_non_cascading(
    copilot_context: tuple[TenantPrincipal, TenantPrincipal, AsyncSession],
) -> None:
    _, _, session = copilot_context

    rows = (
        await session.execute(
            text(
                """
                SELECT conname, confdeltype
                FROM pg_constraint
                WHERE conname IN (
                    'fk_copilot_suggestions_tenant_case',
                    'fk_copilot_citations_tenant',
                    'fk_copilot_citations_tenant_suggestion'
                )
                """
            )
        )
    ).all()
    delete_actions = {
        str(row.conname): str(row.confdeltype)
        for row in rows
    }

    assert delete_actions == {
        "fk_copilot_suggestions_tenant_case": "a",
        "fk_copilot_citations_tenant": "a",
        "fk_copilot_citations_tenant_suggestion": "a",
    }
    await session.close()
