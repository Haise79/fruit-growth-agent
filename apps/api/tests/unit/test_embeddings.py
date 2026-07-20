from unittest.mock import AsyncMock

import pytest

from fruit_agent.config import get_settings
from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider
from fruit_agent.knowledge.repository import KnowledgeRepository
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


def test_production_without_configured_embedding_provider_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="embedding provider"):
            KnowledgeService(
                AsyncMock(spec=KnowledgeRepository)
            )
    finally:
        get_settings.cache_clear()
