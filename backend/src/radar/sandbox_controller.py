"""Single-process operator entry point: python -m radar.sandbox_controller.

This host-mode entry uses the existing independent systemd watchdog. A Compose
deployment must supply its own independent watchdog proof, not fake systemd.
No application Settings, provider credentials or business database is loaded.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .sandbox_credentials import read_service_token
from .sandbox_executor import DockerCommands, SandboxExecutor
from .sandbox_health import SandboxHealth
from .sandbox_http import controller_app, service_token
from .service_lock import acquire_lock as acquire_lock


def production_app(
    image_id: str,
    token: str,
    lock_path: Path,
    *,
    watchdog: Callable[[], Awaitable[None]] | None = None,
) -> FastAPI:
    service_token(token)
    commands = DockerCommands()
    executor = SandboxExecutor(commands, image_id)
    readiness = (
        SandboxHealth(commands, executor)
        if watchdog is None
        else SandboxHealth(commands, executor, watchdog=watchdog)
    )
    app = controller_app(executor, token, readiness=readiness)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        lock = acquire_lock(lock_path)
        monitor: asyncio.Task[None] | None = None
        try:
            await readiness.startup()
            monitor = asyncio.create_task(readiness.monitor())
            yield
        finally:
            readiness.failed = True
            if monitor is not None:
                monitor.cancel()
                await asyncio.gather(monitor, return_exceptions=True)
            lock.close()

    app.router.lifespan_context = lifespan
    return app


def main() -> None:
    import uvicorn

    # Operator configuration only. The token file is not an executable config;
    # never put the token on argv, in exception messages or in access logs.
    token_path = Path(os.environ["RADAR_SANDBOX_TOKEN_FILE"])
    token = read_service_token(token_path)
    app = production_app(
        os.environ["RADAR_SANDBOX_IMAGE_ID"],
        token,
        Path(f"/run/user/{os.getuid()}/ai-radar-sandbox-controller.lock"),
    )
    uvicorn.run(app, host="127.0.0.1", port=8092, workers=1, access_log=False)


if __name__ == "__main__":
    main()
