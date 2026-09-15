import pytest

from radar.hybrid import hybrid_search, hybrid_search_scoped


@pytest.mark.asyncio
async def test_hard_scope_is_complete_and_both_channels_are_isolated() -> None:
    async def keyword(_query: str, _scope: list[str], _limit: int) -> list[str]:
        return ["outside", "a", "b"]

    async def semantic(_query: str, _scope: list[str], _limit: int) -> list[str]:
        return ["outside", "b", "c"]

    result = await hybrid_search("模型", ["a", "b", "c", "d"], keyword, semantic)
    assert result.scope_ids == ["a", "b", "c", "d"]
    assert result.ranked_ids == ["b", "a", "c"]
    assert result.retrieval_mode == "hybrid"
    assert result.degraded_reason is None


@pytest.mark.asyncio
async def test_embedding_failure_degrades_without_becoming_empty_scope() -> None:
    async def keyword(_query: str, _scope: list[str], _limit: int) -> list[str]:
        return ["a"]

    async def semantic(_query: str, _scope: list[str], _limit: int) -> list[str]:
        raise TimeoutError

    result = await hybrid_search("模型", ["a", "b"], keyword, semantic)
    assert result.scope_ids == ["a", "b"]
    assert result.ranked_ids == ["a"]
    assert result.degraded_reason == "embedding_failed"


@pytest.mark.asyncio
async def test_database_scoped_candidates_fuse_without_materialized_scope_ids() -> None:
    async def keyword(_query: str, _limit: int) -> list[str]:
        return ["a", "b", "a"]

    async def semantic(_query: str, _limit: int) -> list[str]:
        return ["b", "c"]

    result = await hybrid_search_scoped("model", 100_000, keyword, semantic)
    assert result.scope_ids == []
    assert result.ranked_ids == ["b", "a", "c"]
    assert result.keyword_count == 2
    assert result.semantic_count == 2
    assert result.degraded_reason is None
