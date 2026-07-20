from unittest.mock import AsyncMock
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from fruit_agent.config import get_settings
from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.schemas import KnowledgeItemCreate
from fruit_agent.knowledge.service import KnowledgeService


def test_deterministic_embedding_is_stable_and_has_expected_dimension() -> None:
    provider = DeterministicEmbeddingProvider()

    first = provider.embed("Fuji apples from Yantai")
    second = provider.embed("Fuji apples from Yantai")

    assert first == second
    assert len(first) == 1536
    assert all(isinstance(value, float) for value in first)
    assert provider.model_name == "deterministic-sha256"
    assert provider.model_version == "1"


@pytest.mark.asyncio
async def test_read_only_knowledge_service_does_not_require_embedding_provider() -> None:
    repository = AsyncMock(spec=KnowledgeRepository)
    repository.list_items.return_value = []

    service = KnowledgeService(repository, None)

    assert await service.list_items(uuid4()) == []


@pytest.mark.asyncio
async def test_production_read_only_service_allows_missing_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    repository = AsyncMock(spec=KnowledgeRepository)
    repository.list_items.return_value = []
    try:
        assert await KnowledgeService(repository, None).list_items(uuid4()) == []
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_production_rejects_deterministic_embedding_for_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    repository = AsyncMock(spec=KnowledgeRepository)
    repository.has_active_member.return_value = True
    try:
        with pytest.raises(RuntimeError, match="embedding provider"):
            await KnowledgeService(
                repository,
                DeterministicEmbeddingProvider(),
            ).create_item(
                tenant_id=uuid4(),
                item=KnowledgeItemCreate(
                    knowledge_type="faq",
                    content="Safe content",
                    source_name="Source",
                    responsible_user_id=uuid4(),
                    valid_until=datetime.now(UTC) + timedelta(days=1),
                ),
            )
    finally:
        get_settings.cache_clear()
