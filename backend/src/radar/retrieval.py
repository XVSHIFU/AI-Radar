from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

SEARCH_CONFIG_VERSION = "cjk-bigram-v1"
_TOKEN = re.compile(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*|[\u3400-\u9fff]+", re.IGNORECASE)


def search_document(*parts: str) -> str:
    tokens: list[str] = []
    for raw in parts:
        for match in _TOKEN.findall(raw.casefold()):
            if "\u3400" <= match[0] <= "\u9fff":
                chars = list(match)
                tokens.extend(
                    chars
                    if len(chars) == 1
                    else ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]
                )
            else:
                tokens.append(match)
    return " ".join(dict.fromkeys(tokens))


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, constant: int = 60
) -> list[tuple[str, float]]:
    if constant <= 0:
        raise ValueError("constant must be positive")
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, event_id in enumerate(dict.fromkeys(ranking), start=1):
            scores[event_id] = scores.get(event_id, 0.0) + 1.0 / (constant + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


@dataclass(frozen=True)
class EmbeddingProfile:
    provider: str
    model_id: str
    revision: str
    dimension: int
    normalize: bool
    input_template_version: str

    @property
    def fingerprint(self) -> str:
        raw = "\0".join(
            (
                self.provider,
                self.model_id,
                self.revision,
                str(self.dimension),
                str(self.normalize),
                self.input_template_version,
            )
        )
        return hashlib.sha256(raw.encode()).hexdigest()


class EmbeddingProvider(Protocol):
    profile: EmbeddingProfile

    async def embed_query(self, text: str) -> Sequence[float]: ...


class EmbeddingDimensionMismatch(ValueError):
    pass


async def checked_query_embedding(provider: EmbeddingProvider, text: str) -> list[float]:
    vector = [float(value) for value in await provider.embed_query(text)]
    if len(vector) != provider.profile.dimension:
        raise EmbeddingDimensionMismatch(
            f"profile expects {provider.profile.dimension} dimensions, "
            f"provider returned {len(vector)}"
        )
    return vector
