"""Private controller API. Run as one process, separately from the public API.

Only this process receives the Docker socket. The bearer is an operator-owned
service credential, never a model tool argument or a public research capability.
"""

from __future__ import annotations

import asyncio
import hmac
import re
import time
from typing import Any, Protocol
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response

from .research_guard import ResearchRejected
from .research_stream import strict_json
from .sandbox_protocol import MAX_INPUT_BYTES, SandboxResult, sandbox_input, sandbox_wire


class Executor(Protocol):
    async def run(self, code: str, datasets: list[dict[str, Any]]) -> SandboxResult: ...


def service_token(token: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token):
        raise ValueError("a random service token of at least 256 bits is required")
    return token


def controller_app(executor: Executor, token: str) -> FastAPI:
    expected = "Bearer " + service_token(token)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    # Monotonic tombstones include failed/cancelled jobs; no transparent retries.
    seen: dict[str, float] = {}
    active = 0

    def authenticate(request: Request) -> None:
        values = request.headers.getlist("authorization")
        if len(values) != 1 or not hmac.compare_digest(values[0].encode(), expected.encode()):
            raise HTTPException(401, detail={"code": "UNAUTHORIZED"})

    @app.post("/v1/execute")
    async def execute(request: Request) -> Response:
        nonlocal active
        authenticate(request)
        if active >= 2:
            raise HTTPException(429, detail={"code": "RUN_BUSY"})
        active += 1
        task: asyncio.Task[SandboxResult] | None = None
        disconnected: asyncio.Task[None] | None = None
        try:
            body = bytearray()
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    if len(body) + len(chunk) > MAX_INPUT_BYTES + 128:
                        raise ResearchRejected("RESOURCE_LIMIT")
                    body.extend(chunk)
            value = strict_json(bytes(body).decode())
            if not isinstance(value, dict) or set(value) != {"job_id", "code", "datasets"}:
                raise ResearchRejected("INVALID_ARGUMENT")
            job_id = value["job_id"]
            if not isinstance(job_id, str) or str(UUID(job_id)) != job_id:
                raise ResearchRejected("INVALID_ARGUMENT")
            sandbox_input(value["code"], value["datasets"])
            now = time.monotonic()
            for key, expiry in list(seen.items()):
                if expiry <= now:
                    del seen[key]
            if job_id in seen:
                raise ResearchRejected("JOB_REPLAY")
            if len(seen) >= 2048:
                raise ResearchRejected("RUN_BUSY")
            seen[job_id] = now + 600
            task = asyncio.create_task(executor.run(value["code"], value["datasets"]))

            # Read disconnect directly after the complete body. is_disconnected()
            # uses an immediate cancel scope which can swallow external cancellation.
            async def watch_disconnect() -> None:
                while True:
                    if (await request.receive())["type"] == "http.disconnect":
                        return

            disconnected = asyncio.create_task(watch_disconnect())
            async with asyncio.timeout(32):
                done, _ = await asyncio.wait(
                    {task, disconnected}, return_when=asyncio.FIRST_COMPLETED
                )
                if disconnected in done:
                    raise ResearchRejected("CLIENT_DISCONNECTED")
                result = await task
            return Response(
                sandbox_wire(result),
                media_type="application/json",
                headers={"Cache-Control": "no-store"},
            )
        except ResearchRejected as exc:
            status = {
                "INVALID_ARGUMENT": 400,
                "RESOURCE_LIMIT": 413,
                "JOB_REPLAY": 409,
                "RUN_BUSY": 429,
            }.get(exc.code, 503)
            raise HTTPException(status, detail={"code": exc.code}) from exc
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise HTTPException(400, detail={"code": "INVALID_ARGUMENT"}) from exc
        except TimeoutError as exc:
            raise HTTPException(504, detail={"code": "EXECUTION_TIMEOUT"}) from exc
        finally:
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if disconnected is not None:
                disconnected.cancel()
                await asyncio.gather(disconnected, return_exceptions=True)
            active -= 1

    return app
