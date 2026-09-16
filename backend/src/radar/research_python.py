"""Run-local authorization for Python; model arguments contain only dataset IDs.

The operator attaches this adapter to a verified research session. Public tool
registration stays disabled until policy/runtime/SSE integration is accepted.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .research_artifacts import ArtifactStore
from .research_guard import ResearchGuard, ResearchRejected, canonical
from .sandbox_client import SandboxClient
from .sandbox_protocol import sandbox_input


class PythonArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str = Field(min_length=1, max_length=16384)
    dataset_ids: list[str] = Field(min_length=1, max_length=4)


class ResearchPython:
    def __init__(
        self,
        guard: ResearchGuard,
        datasets: dict[str, dict[str, Any]],
        client: SandboxClient,
        artifacts: ArtifactStore,
    ) -> None:
        self.guard, self.datasets = guard, datasets
        self.client, self.artifacts = client, artifacts
        self._used = False

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.guard.check(self.guard.capability)
        try:
            args = PythonArguments.model_validate(arguments)
        except ValidationError as exc:
            raise ResearchRejected("INVALID_ARGUMENT") from exc
        ids = tuple(args.dataset_ids)
        if len(set(ids)) != len(ids) or any(key not in self.datasets for key in ids):
            raise ResearchRejected("DATASET_NOT_FOUND")
        # Only the server's current scope registry can provide input rows. Take a
        # detached snapshot so no later mutation can change the submitted data.
        datasets = json.loads(canonical([self.datasets[key] for key in ids]))
        sandbox_input(args.code, datasets)
        if self._used:
            raise ResearchRejected("PYTHON_BUDGET_EXCEEDED")
        self._used = True
        seconds = (self.guard.deadline - datetime.now(UTC)).total_seconds()
        try:
            async with asyncio.timeout(max(0, seconds)):
                result = await self.client.run(self.guard.run_id, args.code, datasets)
        except TimeoutError as exc:
            raise ResearchRejected("RUN_EXPIRED") from exc
        self.guard.check(self.guard.capability)
        records = self.artifacts.publish(self.guard.owner_hash, self.guard.run_id, ids, result)
        # Keep the model's tool response within its independent 32 KiB budget.
        stdout = result.stdout.encode()
        return {
            "stdout": stdout[:16384].decode("utf-8", errors="ignore"),
            "stdout_truncated": len(stdout) > 16384,
            "dataset_ids": list(ids),
            "artifacts": [
                {
                    "id": str(item.id),
                    "name": item.file.name,
                    "mime": item.file.mime,
                    "size_bytes": len(item.file.content),
                    "expires_in_seconds": 900,
                    "download_url": (f"/api/v1/assistant/runs/{item.run_id}/artifacts/{item.id}"),
                }
                for item in records
            ],
        }
