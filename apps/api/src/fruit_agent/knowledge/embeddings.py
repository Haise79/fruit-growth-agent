from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from fruit_agent.knowledge.models import EMBEDDING_DIMENSION


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class DeterministicEmbeddingProvider:
    """Development embedding provider with repeatable, fixed-size vectors."""

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
