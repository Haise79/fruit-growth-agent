from typing import cast

from fastapi import Request

from fruit_agent.knowledge.embeddings import EmbeddingProvider


def get_embedding_provider(request: Request) -> EmbeddingProvider | None:
    provider = getattr(request.app.state, "embedding_provider", None)
    return cast(EmbeddingProvider | None, provider)
