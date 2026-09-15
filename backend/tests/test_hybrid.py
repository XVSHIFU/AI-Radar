import pytest

from radar.hybrid import hybrid_search


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
