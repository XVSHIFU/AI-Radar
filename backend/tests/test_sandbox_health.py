import asyncio
import json
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_executor import CommandResult, SandboxExecutor
from radar.sandbox_health import RUNTIME, SandboxHealth, watchdog_properties
from radar.sandbox_http import controller_app

IMAGE = "sha256:" + "a" * 64
TOKEN = "a" * 43


def setup_health():
    commands = AsyncMock()

    async def execute(args, **kwargs):
        if args[0] == "info":
            return CommandResult(
                0,
                json.dumps(
                    {
                        "runsc": {
                            "status": {"features": "runtime may publish additional metadata"},
                            "path": str(RUNTIME),
                            "runtimeArgs": ["--platform=systrap"],
                        }
                    }
                ).encode(),
            )
        if args[0] == "image":
            return CommandResult(0, IMAGE.encode())
        return CommandResult(0, b"")

    commands.execute.side_effect = execute
    executor = SandboxExecutor(commands, IMAGE)
    watchdog = AsyncMock()
    health = SandboxHealth(commands, executor, watchdog, lambda: None)
    return commands, executor, watchdog, health


async def test_startup_cleans_before_publishing_and_checks_watchdog():
    commands, executor, watchdog, health = setup_health()
    with pytest.raises(ResearchRejected):
        health.snapshot()
    await health.startup()
    assert health.snapshot()["image_id"] == IMAGE
    assert watchdog.await_count == 2
    assert [call.args[0][0] for call in commands.execute.await_args_list] == [
        "info",
        "image",
        "ps",
        "ps",
        "info",
        "image",
    ]
    executor._healthy = False
    with pytest.raises(ResearchRejected):
        health.snapshot()


@pytest.mark.parametrize("failure", ["runtime", "image", "watchdog", "binary"])
async def test_attestation_failure_latches_closed(failure):
    commands, _, watchdog, health = setup_health()
    await health.startup()
    original = commands.execute.side_effect

    async def altered(args, **kwargs):
        if args[0] == "info" and failure == "runtime":
            return CommandResult(0, b'{"runsc":{"path":"/usr/bin/runc"}}')
        if args[0] == "image" and failure == "image":
            return CommandResult(0, b"sha256:wrong")
        return await original(args, **kwargs)

    commands.execute.side_effect = altered
    if failure == "watchdog":
        watchdog.side_effect = ResearchRejected("SANDBOX_WATCHDOG_FAILED")
    if failure == "binary":

        def reject():
            raise ResearchRejected("SANDBOX_UNAVAILABLE")

        health.binary = reject
    with pytest.raises(ResearchRejected):
        await health.refresh()
    with pytest.raises(ResearchRejected):
        health.snapshot()
    watchdog.side_effect = None
    commands.execute.side_effect = original
    health.binary = lambda: None
    with pytest.raises(ResearchRejected):
        await health.refresh()


async def test_fresh_orphan_blocks_startup_without_force_deleting():
    commands, _, _, health = setup_health()
    # Reaper listing is empty, second scan detects a concurrent/recent orphan.
    commands.execute.side_effect = [
        CommandResult(
            0,
            json.dumps(
                {
                    "runsc": {
                        "status": {"features": "runtime may publish additional metadata"},
                        "path": str(RUNTIME),
                        "runtimeArgs": ["--platform=systrap"],
                    }
                }
            ).encode(),
        ),
        CommandResult(0, IMAGE.encode()),
        CommandResult(0, b""),
        CommandResult(0, b"aaaaaaaaaaaa"),
    ]
    with pytest.raises(ResearchRejected, match="SANDBOX_ORPHANS_REMAIN"):
        await health.startup()
    assert health.failed
    assert not any(c.args[0][0] == "rm" for c in commands.execute.await_args_list)


@pytest.mark.parametrize("age", [46, -1, 100])
def test_watchdog_stale_future_never_run_rejected(age):
    stamp = (100 - age) * 1000000
    raw = f"Result=success\nExecMainStatus=0\nExecMainExitTimestampMonotonic={stamp}\n"
    with pytest.raises(ResearchRejected):
        watchdog_properties(raw.encode(), 100)


def test_watchdog_success_and_failed_exit():
    watchdog_properties(
        b"Result=success\nExecMainStatus=0\nExecMainExitTimestampMonotonic=95000000\n", 100
    )
    for raw in [
        b"Result=exit-code\nExecMainStatus=1\nExecMainExitTimestampMonotonic=95000000",
        b"Result=success\nResult=success",
        b"bad",
        b"",
    ]:
        with pytest.raises(ResearchRejected):
            watchdog_properties(raw, 100)


async def test_authenticated_health_and_execute_share_fail_closed_lease():
    _, executor, _, health = setup_health()
    executor.run = AsyncMock()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(executor, TOKEN, readiness=health)),
        base_url="http://controller",
    ) as client:
        assert (await client.get("/health")).status_code == 401
        client.headers["Authorization"] = "Bearer " + TOKEN
        assert (await client.get("/health")).status_code == 503
        await health.startup()
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        health.checked_at = time.monotonic() - 13
        assert (await client.get("/health")).status_code == 503
        assert (await client.post("/v1/execute", content=b"bad")).status_code == 503
        executor.run.assert_not_awaited()


async def test_monitor_cancel_is_not_swallowed():
    _, _, _, health = setup_health()
    task = asyncio.create_task(health.monitor())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
