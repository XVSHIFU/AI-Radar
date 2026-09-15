from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from .retrieval import reciprocal_rank_fusion

CandidateRetriever = Callable[[str, Sequence[str], int], Awaitable[Sequence[str]]]


@dataclass(frozen=True)
class HybridResult:
    scope_ids: list[str]
    ranked_ids: list[str]
    keyword_count: int
    semantic_count: int
    retrieval_mode: str
    degraded_reason: str | None


async def hybrid_search(
    query: str,
    hard_scope_ids: Sequence[str],
    keyword: CandidateRetriever,
    semantic: CandidateRetriever | None,
    *,
    candidate_limit: int = 60,
) -> HybridResult:
    """Rank candidates while preserving the complete structured scope separately."""
    scope = list(dict.fromkeys(hard_scope_ids))
    allowed = set(scope)
    keyword_ids = [
        item
        for item in dict.fromkeys(await keyword(query, scope, candidate_limit))
        if item in allowed
    ][:candidate_limit]
    semantic_ids: list[str] = []
    degraded_reason: str | None = None
    if semantic is None:
        degraded_reason = "embedding_unavailable"
    else:
        try:
            semantic_ids = [
                item
                for item in dict.fromkeys(await semantic(query, scope, candidate_limit))
                if item in allowed
            ][:candidate_limit]
        except Exception:
            degraded_reason = "embedding_failed"
    rankings = [keyword_ids]
    if semantic_ids:
        rankings.append(semantic_ids)
    ranked = [item[0] for item in reciprocal_rank_fusion(rankings)]
    return HybridResult(
        scope_ids=scope,
        ranked_ids=ranked,
        keyword_count=len(keyword_ids),
        semantic_count=len(semantic_ids),
        retrieval_mode="hybrid" if semantic_ids else "keyword",
        degraded_reason=degraded_reason,
    )
