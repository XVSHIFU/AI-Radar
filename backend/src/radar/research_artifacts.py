"""Bounded, short-lived artifacts. Owners come from signed cookies, never IPs."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response

from .public_assistant import COOKIE
from .research_guard import ResearchRejected
from .sandbox_protocol import (
    MAX_ARTIFACT_BYTES,
    SandboxArtifact,
    SandboxResult,
    sandbox_result,
    sandbox_wire,
)

router = APIRouter()


@dataclass(frozen=True)
class ArtifactRecord:
    id: UUID
    owner: str
    run_id: UUID
    dataset_ids: tuple[str, ...]
    expires: float
    file: SandboxArtifact


class ArtifactStore:
    """One API worker; bounded RAM, 15 minute TTL, restart invalidates links.

    Reject on capacity instead of evicting another user's current results. P5
    must preserve single ownership routing or replace this with a shared store.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._records: dict[UUID, ArtifactRecord] = {}
        self._runs: dict[UUID, float] = {}

    def _expire(self) -> None:
        now = self.clock()
        self._records = {key: item for key, item in self._records.items() if item.expires > now}
        self._runs = {key: expiry for key, expiry in self._runs.items() if expiry > now}

    async def reap_forever(self) -> None:
        while True:
            await asyncio.sleep(30)
            self._expire()

    def publish(
        self, owner: str, run_id: UUID, dataset_ids: tuple[str, ...], result: SandboxResult
    ) -> tuple[ArtifactRecord, ...]:
        if not re.fullmatch(r"[a-f0-9]{64}", owner) or not 1 <= len(dataset_ids) <= 4:
            raise ResearchRejected("INVALID_ARGUMENT")
        if len(set(dataset_ids)) != len(dataset_ids) or any(
            not isinstance(value, str)
            or not re.fullmatch(
                r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", value
            )
            for value in dataset_ids
        ):
            raise ResearchRejected("INVALID_ARGUMENT")
        result = sandbox_result(sandbox_wire(result))
        self._expire()
        if run_id in self._runs:
            raise ResearchRejected("JOB_REPLAY")
        incoming = sum(len(item.content) for item in result.artifacts)
        if len(result.artifacts) > 8 or incoming > MAX_ARTIFACT_BYTES:
            raise ResearchRejected("RESOURCE_LIMIT")
        if (
            len(self._runs) >= 1024
            or len(self._records) + len(result.artifacts) > 1024
            or sum(len(item.file.content) for item in self._records.values()) + incoming
            > 32 * MAX_ARTIFACT_BYTES
        ):
            raise ResearchRejected("RESOURCE_LIMIT")
        # Called only with sandbox_result-validated bytes, after the run guard
        # recheck. Synchronous commit cannot interleave with another publisher.
        expiry = self.clock() + 900
        records = tuple(
            ArtifactRecord(uuid4(), owner, run_id, dataset_ids, expiry, item)
            for item in result.artifacts
        )
        self._records.update((item.id, item) for item in records)
        self._runs[run_id] = expiry
        return records

    def get(self, owner: str, run_id: UUID, artifact_id: UUID) -> ArtifactRecord | None:
        self._expire()
        item = self._records.get(artifact_id)
        return item if item and item.owner == owner and item.run_id == run_id else None


@router.get("/api/v1/assistant/runs/{run_id}/artifacts/{artifact_id}")
async def download(request: Request, run_id: UUID, artifact_id: UUID) -> Response:
    identity = getattr(request.app.state, "public_identity", None)
    store = getattr(request.app.state, "research_artifacts", None)
    owner = identity.subject(request.cookies.get(COOKIE)) if identity else None
    item = store.get(owner, run_id, artifact_id) if store and owner else None
    if item is None:
        raise HTTPException(
            404, detail={"code": "ARTIFACT_NOT_FOUND"}, headers={"Cache-Control": "no-store"}
        )
    return Response(
        item.file.content,
        media_type=item.file.mime,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="{item.file.name}"',
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )
