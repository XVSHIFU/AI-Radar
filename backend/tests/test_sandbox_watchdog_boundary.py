import asyncio
import json
from io import BytesIO
from unittest.mock import AsyncMock

import httpx
import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_executor import CommandResult
from radar.sandbox_watchdog import WatchdogState, check_watchdog, watchdog_app

TOKEN = "a" * 43
PROOF = {
    "protocol": 1,
    "role": "independent-watchdog",
    "status": "ready",
    "sweep_age_seconds": 0,
}


@pytest.mark.parametrize(
    "raw",
    [
        b"[" * 1500 + b"]" * 1500,
        json.dumps({**PROOF, "sweep_age_seconds": 10**400}).encode(),
        b'{"protocol":1,"protocol":1}',
        b'{"sweep_age_seconds":NaN}',
        b"\xff",
    ],
)
async def test_malformed_proof_always_becomes_controlled_rejection(raw):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=raw))
    ) as client:
        with pytest.raises(ResearchRejected, match="SANDBOX_WATCHDOG_FAILED"):
            await check_watchdog(client, TOKEN)


@pytest.mark.parametrize("local,origin", [(False, "sandbox-watchdog"), (True, "127.0.0.1")])
async def test_valid_proof_uses_only_fixed_origin_and_private_credential(local, origin):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=PROOF)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        await check_watchdog(client, TOKEN, local=local)
    assert len(seen) == 1
    request = seen[0]
    assert request.url.host == origin
    assert request.url.port == 8093
    assert request.url.path == "/health"
    assert request.headers["authorization"] == "Bearer " + TOKEN
    assert request.headers["accept-encoding"] == "identity"


async def test_health_read_has_an_overall_deadline(monkeypatch):
    import radar.sandbox_watchdog as watchdog

    real_timeout = asyncio.timeout
    monkeypatch.setattr(watchdog.asyncio, "timeout", lambda _: real_timeout(0.02))

    async def handle(request):
        await asyncio.Event().wait()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ResearchRejected, match="SANDBOX_WATCHDOG_FAILED"):
            await check_watchdog(client, TOKEN)


async def test_failed_startup_releases_watchdog_lock(monkeypatch, tmp_path):
    import radar.sandbox_watchdog as watchdog

    lock = BytesIO()
    monkeypatch.setattr(watchdog, "acquire_lock", lambda _: lock)
    commands = AsyncMock()
    commands.execute.return_value = CommandResult(1, b"")
    state = WatchdogState(commands)
    app = watchdog_app(state, TOKEN, tmp_path / "lock")
    with pytest.raises(ResearchRejected):
        async with app.router.lifespan_context(app):
            pytest.fail("must not start serving before the first successful sweep")
    assert state.failed
    assert lock.closed


async def test_watchdog_shutdown_joins_monitor_and_invalidates_health(monkeypatch, tmp_path):
    import radar.sandbox_watchdog as watchdog

    lock = BytesIO()
    monkeypatch.setattr(watchdog, "acquire_lock", lambda _: lock)
    commands = AsyncMock()
    commands.execute.return_value = CommandResult(0, b"")
    state = WatchdogState(commands)
    started, stopped = asyncio.Event(), asyncio.Event()

    async def monitor():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(state, "monitor", monitor)
    app = watchdog_app(state, TOKEN, tmp_path / "lock")
    async with app.router.lifespan_context(app):
        await started.wait()
        assert state.snapshot()["status"] == "ready"
    assert stopped.is_set()
    assert lock.closed
    with pytest.raises(ResearchRejected):
        state.snapshot()
