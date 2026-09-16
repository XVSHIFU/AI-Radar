"""Public API side of the sandbox boundary: HTTP only, no Docker imports."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import httpx

from .research_guard import ResearchRejected, canonical
from .sandbox_protocol import (
    MAX_RESPONSE_BYTES,
    SandboxResult,
    sandbox_input,
    sandbox_result,
)


class SandboxClient:
    def __init__(self, client: httpx.AsyncClient, url: str, token: str):
        # Fixed operator destinations, not arbitrary model/user-supplied URLs.
        if url not in {"http://127.0.0.1:8092", "http://sandbox-controller:8092"}:
            raise ValueError("private sandbox controller address required")
        if (
            not 43 <= len(token) <= 128
            or not token.isascii()
            or any(not (c.isalnum() or c in "_-") for c in token)
        ):
            raise ValueError("sandbox service token required")
        self.client, self.url, self.token = client, url, token

    async def run(self, job_id: UUID, code: str, datasets: list[dict[str, Any]]) -> SandboxResult:
        sandbox_input(code, datasets)
        payload = canonical({"job_id": str(job_id), "code": code, "datasets": datasets}).encode()
        try:
            async with asyncio.timeout(35):
                async with self.client.stream(
                    "POST",
                    self.url + "/v1/execute",
                    content=payload,
                    headers={
                        "Authorization": "Bearer " + self.token,
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                    },
                    timeout=35,
                    follow_redirects=False,
                ) as response:
                    if response.status_code != 200:
                        raise ResearchRejected("SANDBOX_UNAVAILABLE")
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise ResearchRejected("EXECUTION_FAILED")
                    raw = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ResearchRejected("RESOURCE_LIMIT")
                        raw.extend(chunk)
                    # Revalidate all artifacts outside the Docker-owning controller.
                    return sandbox_result(bytes(raw))
        except (httpx.HTTPError, TimeoutError) as exc:
            raise ResearchRejected("SANDBOX_UNAVAILABLE") from exc
