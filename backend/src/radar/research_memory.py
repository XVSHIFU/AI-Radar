"""Optional, single-request browser summary. No server-side transcript storage."""

from __future__ import annotations

import json
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoryReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    index: int = Field(ge=1, le=60)
    evidence_id: str | None = Field(default=None, max_length=36)
    dataset_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def identifiers(self) -> Self:
        for value in (self.evidence_id, self.dataset_id):
            if value is not None and str(UUID(value)) != value:
                raise ValueError("memory references must use canonical UUIDs")
        return self


class MemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    turn_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    question_excerpt: str = Field(max_length=120)
    answer_excerpt: str = Field(max_length=240)
    scope_excerpt: str = Field(max_length=80)
    unresolved: bool
    citations: list[MemoryReference] = Field(max_length=2)


class ConversationMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    entries: list[MemoryEntry] = Field(max_length=6)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        try:
            raw = json.dumps(
                self.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        except UnicodeEncodeError as exc:
            raise ValueError("invalid Unicode in memory") from exc
        # Conservative token upper bound, including JSON escaping and metadata.
        if len(raw) > 1200:
            raise ValueError("memory must fit the 1200-byte conservative token budget")
        ids = [entry.turn_id for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate memory turn")
        return self


class ReplyPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    language: Literal["auto", "zh", "en"] = "auto"
    length: Literal["concise", "detailed"] = "concise"


def prompt_memory(
    memory: ConversationMemory | None, consent: str | None
) -> dict[str, object] | None:
    # Defense in depth: even direct callers cannot attach a summary implicitly.
    if consent != "send_once" or memory is None or not memory.entries:
        return None
    return {
        "kind": "untrusted_extractive_summary",
        "recheck_required": True,
        "entries": memory.model_dump(mode="json", exclude_none=True)["entries"],
    }
