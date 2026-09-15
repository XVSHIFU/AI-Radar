"""Operator-side execution controller; never import into the public API router.

The Docker socket belongs to a separate trusted sandbox controller. Model code
is sent only on stdin and never interpolated into commands, paths or options.
This module does not enable the public Python tool or attest isolation itself.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from .research_guard import ResearchRejected
from .sandbox_protocol import MAX_RESPONSE_BYTES, SandboxResult, sandbox_input, sandbox_result


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: bytes


class Commands(Protocol):
    async def execute(
        self,
        arguments: list[str],
        *,
        payload: bytes = b"",
        timeout: float = 5,
        output_limit: int = 65536,
    ) -> CommandResult: ...


class DockerCommands:
    async def execute(
        self,
        arguments: list[str],
        *,
        payload: bytes = b"",
        timeout: float = 5,
        output_limit: int = 65536,
    ) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/docker",
            "--host=unix:///run/docker.sock",
            *arguments,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
        assert (
            process.stdin is not None and process.stdout is not None and process.stderr is not None
        )

        async def read(stream: asyncio.StreamReader, limit: int) -> bytes:
            parts, size = [], 0
            while part := await stream.read(min(16384, limit - size + 1)):
                size += len(part)
                if size > limit:
                    raise ResearchRejected("RESOURCE_LIMIT")
                parts.append(part)
            return b"".join(parts)

        async def write() -> None:
            assert process.stdin is not None
            try:
                process.stdin.write(payload)
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                process.stdin.close()

        tasks = [
            asyncio.create_task(read(process.stdout, output_limit)),
            asyncio.create_task(read(process.stderr, 65536)),
            asyncio.create_task(write()),
        ]
        try:
            async with asyncio.timeout(timeout):
                values = await asyncio.gather(*tasks)
                code = await process.wait()
                return CommandResult(code, values[0] or b"")
        finally:
            for task in tasks:
                task.cancel()
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await asyncio.gather(*tasks, return_exceptions=True)
            await process.wait()


class SandboxExecutor:
    """Fixed limits from policy.json. Separate authenticated gateway is still required.

    A failed deletion latches this instance closed. Deployment must additionally
    reap labelled orphan tasks on startup and enforce an independent watchdog.
    """

    def __init__(self, commands: Commands, image_id: str):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ValueError("reviewed local image digest required")
        self.commands, self.image_id = commands, image_id
        self._active = 0
        self._healthy = True

    def _create(self, name: str) -> list[str]:
        return [
            "create",
            "--name",
            name,
            "--label",
            "ai-radar.sandbox=task",
            "--runtime=runsc",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--user=65532:65532",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--cpus=1",
            "--memory=256m",
            "--memory-swap=256m",
            "--pids-limit=32",
            "--ipc=none",
            "--cgroupns=private",
            "--ulimit=cpu=10:10",
            "--ulimit=nofile=128:128",
            "--ulimit=core=0:0",
            "--ulimit=fsize=1048576:1048576",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777",
            "--restart=no",
            "--log-driver=none",
            "--no-healthcheck",
            "--stop-timeout=0",
            "--interactive",
            "--workdir=/tmp",
            "--entrypoint=python",
            self.image_id,
            "-B",
            "/opt/worker.py",
        ]

    async def _remove(self, name: str) -> None:
        try:
            result = await self.commands.execute(["rm", "--force", "--volumes", name], timeout=5)
            if result.code:
                raise ResearchRejected("SANDBOX_CLEANUP_FAILED")
        except BaseException:
            self._healthy = False
            raise

    async def run(self, code: str, datasets: list[dict[str, Any]]) -> SandboxResult:
        payload = sandbox_input(code, datasets)
        if not self._healthy:
            raise ResearchRejected("SANDBOX_UNAVAILABLE")
        if self._active >= 2:
            raise ResearchRejected("RUN_BUSY")
        self._active += 1
        name = "radar-python-" + uuid4().hex
        try:
            # The create CLI may fail after the daemon creates the object: cleanup
            # is attempted even on an uncertain create outcome.
            try:
                async with asyncio.timeout(25):
                    created = await self.commands.execute(self._create(name), timeout=5)
                    if created.code:
                        raise ResearchRejected("SANDBOX_UNAVAILABLE")
                    execution = await self.commands.execute(
                        ["start", "--attach", "--interactive", name],
                        payload=payload,
                        timeout=10,
                        output_limit=MAX_RESPONSE_BYTES,
                    )
                    if execution.code:
                        raise ResearchRejected("EXECUTION_FAILED")
                    return sandbox_result(execution.stdout)
            except TimeoutError as exc:
                raise ResearchRejected("EXECUTION_TIMEOUT") from exc
            finally:
                cleanup = asyncio.create_task(self._remove(name))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                    raise
        finally:
            self._active -= 1
