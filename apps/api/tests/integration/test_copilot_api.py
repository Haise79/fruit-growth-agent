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
    KnowledgeType,
    MerchantKnowledge,
    ProductSKU,
    ReviewStatus,
)
from fruit_agent.model_gateway.schemas import (
    CopilotAgentOutput,
    CopilotAgentSuggestion,
    CopilotProviderResponse,
    ModelProfile,
)
from fruit_agent.model_gateway.service import ProviderBinding, ProviderUnavailableError


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
                taste="脆甜",
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
