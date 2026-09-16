"""Independent container watchdog, with authenticated and fresh sweep health.

Only this trusted operator process and the controller receive the Docker socket.
Public API, pi and generated Python do not import this module or mount the socket.
"""

from __future__ import annotations

import asyncio
import hmac
import math
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .research_guard import ResearchRejected
from .research_stream import strict_json
from .sandbox_controller import acquire_lock
from .sandbox_credentials import read_service_token
from .sandbox_executor import Commands, DockerCommands
from .sandbox_http import service_token
from .sandbox_reaper import reap_expired

WATCHDOG_ORIGIN = "http://sandbox-watchdog:8093"


class WatchdogState:
    def __init__(self, commands: Commands):
        self.commands = commands
        self.last_success: float | None = None
        self.failed = False

    async def sweep(self) -> None:
        try:
            async with asyncio.timeout(20):
                await reap_expired(self.commands)
            self.last_success = time.monotonic()
        except BaseException:
            self.failed = True
            raise

    def snapshot(self) -> dict[str, Any]:
        age = time.monotonic() - self.last_success if self.last_success is not None else -1
        if self.failed or not 0 <= age <= 30:
            raise ResearchRejected("SANDBOX_WATCHDOG_FAILED")
        return {
            "protocol": 1,
            "role": "independent-watchdog",
            "status": "ready",
            "sweep_age_seconds": age,
        }

    async def monitor(self) -> None:
        while True:
            await asyncio.sleep(5)
            try:
                await self.sweep()
            except (ResearchRejected, OSError, TimeoutError, UnicodeError):
                # Keep trying to clean orphaned work, but readiness remains latched
                # closed until an operator restarts this independent process.
                self.failed = True


def watchdog_app(state: WatchdogState, token: str, lock_path: Path) -> FastAPI:
    expected = "Bearer " + service_token(token)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        lock = acquire_lock(lock_path)
        task = None
        try:
            await state.sweep()
            task = asyncio.create_task(state.monitor())
            yield
        finally:
            state.failed = True
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            lock.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        supplied = request.headers.getlist("authorization")
        if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode(), expected.encode()):
            raise HTTPException(401, detail={"code": "UNAUTHORIZED"})
        try:
            value = state.snapshot()
        except ResearchRejected as exc:
            raise HTTPException(503, detail={"code": "SANDBOX_WATCHDOG_FAILED"}) from exc
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    return app


async def check_watchdog(client: httpx.AsyncClient, token: str, *, local: bool = False) -> None:
    origin = "http://127.0.0.1:8093" if local else WATCHDOG_ORIGIN
    try:
        async with asyncio.timeout(3):
            async with client.stream(
                "GET",
                origin + "/health",
                timeout=2,
                follow_redirects=False,
                headers={
                    "Authorization": "Bearer " + service_token(token),
                    "Accept-Encoding": "identity",
                },
            ) as response:
                if (
                    response.status_code != 200
                    or response.headers.get("content-encoding", "identity") != "identity"
                ):
                    raise ValueError("watchdog unavailable")
                raw = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    if len(raw) + len(chunk) > 4096:
                        raise ValueError("watchdog response limit")
                    raw.extend(chunk)
                value = strict_json(bytes(raw).decode())
                if not isinstance(value, dict) or set(value) != {
                    "protocol",
                    "role",
                    "status",
                    "sweep_age_seconds",
                }:
                    raise ValueError("invalid watchdog proof")
                age = value["sweep_age_seconds"]
                if (
                    type(value["protocol"]) is not int
                    or value["protocol"] != 1
                    or value["role"] != "independent-watchdog"
                    or value["status"] != "ready"
                    or type(age) not in (int, float)
                    or not math.isfinite(age)
                    or not 0 <= age <= 30
                ):
                    raise ValueError("stale watchdog proof")
    except (
        httpx.HTTPError,
        ValueError,
        UnicodeError,
        TimeoutError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise ResearchRejected("SANDBOX_WATCHDOG_FAILED") from exc


async def container_watchdog() -> None:
    token = read_service_token(Path("/run/secrets/watchdog_token"))
    async with httpx.AsyncClient(trust_env=False) as client:
        await check_watchdog(client, token)


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    token = read_service_token(Path("/run/secrets/watchdog_token"))
    if args.check:

        async def check() -> None:
            async with httpx.AsyncClient(trust_env=False) as client:
                await check_watchdog(client, token, local=True)

        try:
            asyncio.run(check())
        except (ResearchRejected, OSError):
            raise SystemExit(1) from None
        return
    app = watchdog_app(
        WatchdogState(DockerCommands()), token, Path("/run/radar-control/watchdog.lock")
    )
    uvicorn.run(app, host="0.0.0.0", port=8093, workers=1, access_log=False)


if __name__ == "__main__":
    main()
