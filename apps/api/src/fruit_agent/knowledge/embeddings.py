from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from fruit_agent.config import get_settings
from fruit_agent.knowledge.models import EMBEDDING_DIMENSION


class EmbeddingProvider(Protocol):
    model_name: str
    model_version: str

    def embed(self, text: str) -> list[float]: ...


class DeterministicEmbeddingProvider:
    """Development embedding provider with repeatable, fixed-size vectors."""

    model_name = "deterministic-sha256"
    model_version = "1"

    def embed(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        encoded = text.encode("utf-8")
        while len(values) < EMBEDDING_DIMENSION:
            digest = sha256(encoded + counter.to_bytes(8, "big")).digest()
            for offset in range(0, len(digest), 4):
                integer = int.from_bytes(digest[offset : offset + 4], "big")
                values.append((integer / 2**31) - 1.0)
                if len(values) == EMBEDDING_DIMENSION:
                    break
            counter += 1
        return values


def default_embedding_provider() -> EmbeddingProvider | None:
    if get_settings().environment.casefold() in {"development", "test"}:
        return DeterministicEmbeddingProvider()
    return None


def embedding_provider_is_allowed(provider: EmbeddingProvider) -> bool:
    return not (
        isinstance(provider, DeterministicEmbeddingProvider)
        and get_settings().environment.casefold() not in {"development", "test"}
    )
