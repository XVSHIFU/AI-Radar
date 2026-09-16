"""Trusted controller checks. Never load in the public API or model runtime."""

from __future__ import annotations

import asyncio
import hashlib
import os
import stat
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .research_guard import ResearchRejected
from .research_stream import strict_json
from .sandbox_executor import Commands, SandboxExecutor
from .sandbox_reaper import reap_expired

RUNTIME = Path("/opt/ai-radar/gvisor/20260907.0/runsc")
RUNTIME_HASH = "3e0df2fa28f6ff5430b004f92573b81b75f442f78c780e0c85fdf6c2d572817a"


def verify_binary() -> None:
    # Operator-owned executable; no user-writable path components or symlinks.
    for path in (RUNTIME, *RUNTIME.parents):
        info = path.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise ResearchRejected("SANDBOX_UNAVAILABLE")
    if not RUNTIME.is_file() or RUNTIME.stat().st_size > 128 * 1024 * 1024:
        raise ResearchRejected("SANDBOX_UNAVAILABLE")
    with RUNTIME.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != RUNTIME_HASH:
            raise ResearchRejected("SANDBOX_UNAVAILABLE")


def watchdog_properties(raw: bytes, now: float) -> None:
    """Require a live timer AND a recently completed successful independent sweep."""
    records: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in records:
            raise ResearchRejected("SANDBOX_WATCHDOG_FAILED")
        records[key] = value
    try:
        age = now - int(records["ExecMainExitTimestampMonotonic"]) / 1_000_000
        if records["Result"] != "success" or records["ExecMainStatus"] != "0":
            raise ValueError("failed sweep")
        if not 0 <= age <= 45 or int(records["ExecMainExitTimestampMonotonic"]) == 0:
            raise ValueError("stale sweep")
    except (KeyError, ValueError) as exc:
        raise ResearchRejected("SANDBOX_WATCHDOG_FAILED") from exc


async def systemctl(*arguments: str) -> bytes:
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/systemctl",
        "--user",
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}"},
    )
    assert process.stdout is not None
    try:
        async with asyncio.timeout(2):
            raw = await process.stdout.read(4097)
            if len(raw) > 4096 or await process.wait() != 0:
                raise ResearchRejected("SANDBOX_WATCHDOG_FAILED")
            return raw
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


async def verify_watchdog() -> None:
    timer = await systemctl("is-active", "ai-radar-sandbox-watchdog.timer")
    if timer.strip() != b"active":
        raise ResearchRejected("SANDBOX_WATCHDOG_FAILED")
    raw = await systemctl(
        "show",
        "ai-radar-sandbox-watchdog.service",
        "--property=Result,ExecMainStatus,ExecMainExitTimestampMonotonic",
    )
    watchdog_properties(raw, time.monotonic())


class SandboxHealth:
    """Fail-closed readiness lease; failed checks latch closed until process restart."""

    def __init__(
        self,
        commands: Commands,
        executor: SandboxExecutor,
        watchdog: Callable[[], Awaitable[None]] = verify_watchdog,
        binary: Callable[[], None] = verify_binary,
    ):
        self.commands, self.executor = commands, executor
        self.watchdog, self.binary = watchdog, binary
        self.checked_at: float | None = None
        self.failed = False
        self.started = False

    async def refresh(self) -> None:
        if self.failed:
            raise ResearchRejected("SANDBOX_UNAVAILABLE")
        try:
            async with asyncio.timeout(8):
                await asyncio.to_thread(self.binary)
                runtime = await self.commands.execute(["info", "--format", "{{json .Runtimes}}"])
                data = strict_json(runtime.stdout.decode())
                entry = data.get("runsc") if isinstance(data, dict) else None
                if (
                    runtime.code
                    or not isinstance(entry, dict)
                    or entry.get("path") != str(RUNTIME)
                    or entry.get("runtimeArgs") != ["--platform=systrap"]
                ):
                    raise ResearchRejected("SANDBOX_UNAVAILABLE")
                image = await self.commands.execute(
                    ["image", "inspect", "--format", "{{.Id}}", self.executor.image_id]
                )
                if image.code or image.stdout.decode().strip() != self.executor.image_id:
                    raise ResearchRejected("SANDBOX_UNAVAILABLE")
                await self.watchdog()
                if not self.executor.healthy:
                    raise ResearchRejected("SANDBOX_UNAVAILABLE")
                self.checked_at = time.monotonic()
        except BaseException:
            self.failed = True
            raise

    async def startup(self) -> None:
        try:
            await self.refresh()
            async with asyncio.timeout(20):
                await reap_expired(self.commands)
                remaining = await self.commands.execute(
                    [
                        "ps",
                        "--all",
                        "--filter",
                        "label=ai-radar.sandbox=task",
                        "--format",
                        "{{.ID}}",
                    ]
                )
                # Fresh leftovers are left to the independent watchdog. Do not
                # publish ready or delete a possibly live job from another worker.
                if remaining.code or remaining.stdout.strip():
                    raise ResearchRejected("SANDBOX_ORPHANS_REMAIN")
            await self.refresh()
            self.started = True
        except BaseException:
            self.failed = True
            raise

    def snapshot(self) -> dict[str, Any]:
        if (
            self.failed
            or not self.started
            or self.checked_at is None
            or not self.executor.healthy
            or not 0 <= time.monotonic() - self.checked_at <= 12
        ):
            raise ResearchRejected("SANDBOX_UNAVAILABLE")
        return {
            "status": "ready",
            "runtime": "gvisor",
            "image_id": self.executor.image_id,
            "runsc_sha256": RUNTIME_HASH,
            "watchdog": "ready",
        }

    async def monitor(self) -> None:
        while True:
            await asyncio.sleep(5)
            await self.refresh()
