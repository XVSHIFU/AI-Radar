import math

import pytest

from radar.retrieval import EmbeddingProfile, checked_query_embedding


class Provider:
    profile = EmbeddingProfile("test", "model", "rev", 3, True, "query-v1")

    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    async def embed_query(self, _text: str) -> list[float]:
        return self.vector


@pytest.mark.asyncio
@pytest.mark.parametrize("vector", [[math.nan, 0.0, 0.0], [math.inf, 0.0, 0.0], [0.0, 0.0, 0.0]])
async def test_embedding_rejects_non_finite_and_zero_vectors(vector: list[float]) -> None:
    with pytest.raises(ValueError):
        await checked_query_embedding(Provider(vector), "query")


@pytest.mark.asyncio
async def test_normalized_profile_rejects_vector_with_wrong_norm() -> None:
    with pytest.raises(ValueError, match="L2-normalized"):
        await checked_query_embedding(Provider([1.0, 1.0, 0.0]), "query")
