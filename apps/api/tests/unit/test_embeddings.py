from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider


def test_deterministic_embedding_is_stable_and_has_expected_dimension() -> None:
    provider = DeterministicEmbeddingProvider()

    first = provider.embed("Fuji apples from Yantai")
    second = provider.embed("Fuji apples from Yantai")

    assert first == second
    assert len(first) == 1536
    assert all(isinstance(value, float) for value in first)
