from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from fruit_agent.copilot.repository import CopilotRepository
from fruit_agent.copilot.service import CopilotService
from fruit_agent.copilot.service import is_relevant_narrative
from fruit_agent.knowledge.models import ProductSKU
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.schemas import ProductSKURead


def test_product_name_overlap_does_not_make_unrelated_document_relevant() -> None:
    assert (
        is_relevant_narrative(
            "苹果应该怎么冷藏保存？",
            "苹果客服团队每周一更新排班和值班负责人。",
        )
        is False
    )


def test_storage_topic_agreement_is_relevant_without_exact_phrase_overlap() -> None:
    assert (
        is_relevant_narrative(
            "苹果应该怎么冷藏保存？",
            "红富士放入冰箱有助于保持脆度。",
        )
        is True
    )


def test_english_store_verb_rejects_retail_store_staff_document() -> None:
    assert (
        is_relevant_narrative(
            "How should I store apples?",
            "Our store staff schedule is updated weekly.",
        )
        is False
    )


def test_english_storage_domain_phrases_remain_relevant() -> None:
    assert (
        is_relevant_narrative(
            "How should I store apples?",
            "Apples should be refrigerated to keep fresh.",
        )
        is True
    )


def test_chinese_taste_query_rejects_unrelated_dessert_sweetness_document() -> None:
    assert (
        is_relevant_narrative(
            "哪款苹果更清脆，值得推荐？",
            "甜品店本周更新甜度测试和员工排班。",
        )
        is False
    )


def test_chinese_multi_character_taste_evidence_remains_relevant() -> None:
    assert (
        is_relevant_narrative(
            "哪款苹果更清脆，值得推荐？",
            "红富士苹果酸甜清脆，适合喜欢爽脆口感的顾客。",
        )
        is True
    )


@pytest.mark.asyncio
async def test_sku_evidence_uses_validated_snapshot_without_requery() -> None:
    tenant_id = uuid4()
    sku = ProductSKU(
        id=uuid4(),
        tenant_id=tenant_id,
        sku_code="APPLE-001",
        name="红富士",
        price=Decimal("29.90"),
        inventory=20,
        source_id=uuid4(),
        valid_until=datetime.now(UTC) + timedelta(days=1),
    )
    knowledge_repository = AsyncMock(spec=KnowledgeRepository)
    knowledge_repository.get_sku_exact.return_value = [sku]
    knowledge_repository.search_semantic.return_value = []
    service = CopilotService(
        repository=AsyncMock(spec=CopilotRepository),
        knowledge_repository=knowledge_repository,
        providers=[],
    )

    skus, _, failure = await service._load_evidence(
        tenant_id=tenant_id,
        selected_sku_codes=["APPLE-001"],
        message="请推荐苹果",
        now=datetime.now(UTC),
    )

    assert failure is None
    assert len(skus) == 1
    assert isinstance(skus[0], ProductSKURead)
    knowledge_repository.get_sku_exact.assert_awaited_once_with(
        tenant_id,
        "APPLE-001",
    )
