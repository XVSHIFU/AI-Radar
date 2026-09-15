import pytest

from radar.retrieval import (
    EmbeddingDimensionMismatch,
    EmbeddingProfile,
    checked_query_embedding,
    reciprocal_rank_fusion,
    search_document,
)


def test_chinese_search_document_uses_overlapping_bigrams_and_ascii_tokens() -> None:
    assert search_document("深度求索发布 DeepSeek-V3.1", "推理模型") == (
        "深度 度求 求索 索发 发布 deepseek-v3.1 推理 理模 模型"
    )


def test_rrf_deduplicates_channels_and_has_stable_tie_breaking() -> None:
    fused = reciprocal_rank_fusion([["b", "a", "b"], ["a", "c"]], constant=10)
    assert [item[0] for item in fused] == ["a", "b", "c"]
    assert fused[0][1] == pytest.approx(1 / 12 + 1 / 11)


@pytest.mark.asyncio
async def test_embedding_profile_rejects_dimension_drift() -> None:
    class Provider:
        profile = EmbeddingProfile("local", "BAAI/bge-m3", "rev", 1024, True, "query-v1")

        async def embed_query(self, text: str) -> list[float]:
            return [0.0] * 3

    with pytest.raises(EmbeddingDimensionMismatch):
        await checked_query_embedding(Provider(), "query")
