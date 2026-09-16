import asyncio
import time
from io import BytesIO
from unittest.mock import AsyncMock

import httpx
import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_executor import CommandResult
from radar.sandbox_watchdog import WatchdogState, check_watchdog, watchdog_app

TOKEN = "a" * 43


def proof(**changes):
    return {
        "protocol": 1,
        "role": "independent-watchdog",
        "status": "ready",
        "sweep_age_seconds": 1.0,
        **changes,
    }


def state():
    commands = AsyncMock()
    commands.execute.return_value = CommandResult(0, b"")
    return WatchdogState(commands)


async def test_health_requires_completed_sweep_and_a_fresh_lease():
    watched = state()
    with pytest.raises(ResearchRejected):
        watched.snapshot()
    await watched.sweep()
    assert watched.snapshot()["status"] == "ready"
    watched.last_success = time.monotonic() - 31
    with pytest.raises(ResearchRejected):
        watched.snapshot()
    watched.last_success = time.monotonic() + 20
    with pytest.raises(ResearchRejected):
        watched.snapshot()


async def test_cleanup_error_latches_unhealthy_even_after_later_success():
    watched = state()
    watched.commands.execute.return_value = CommandResult(1, b"")
    with pytest.raises(ResearchRejected):
        await watched.sweep()
    watched.commands.execute.return_value = CommandResult(0, b"")
    await watched.sweep()
    with pytest.raises(ResearchRejected):
        watched.snapshot()


async def test_sweep_cancellation_is_propagated_and_invalidates_health():
    watched = state()
    watched.commands.execute.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await watched.sweep()
    assert watched.failed


async def test_endpoint_requires_unique_auth_and_returns_no_store(tmp_path):
    watched = state()
    app = watchdog_app(watched, TOKEN, tmp_path / "unused.lock")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://watchdog"
    ) as client:
        assert (await client.get("/health")).status_code == 401
        duplicate = [("Authorization", "Bearer " + TOKEN)] * 2
        assert (await client.get("/health", headers=duplicate)).status_code == 401
        client.headers["Authorization"] = "Bearer " + TOKEN
        assert (await client.get("/health")).status_code == 503
        await watched.sweep()
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "changes",
    [
        {"sweep_age_seconds": 31},
        {"sweep_age_seconds": -1},
        {"sweep_age_seconds": True},
        {"sweep_age_seconds": "1"},
        {"status": "failed"},
        {"protocol": True},
        {"role": "controller"},
        {"unexpected": 1},
    ],
)
async def test_controller_rejects_stale_or_forged_proof(changes):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=proof(**changes)))
    ) as client:
        with pytest.raises(ResearchRejected, match="SANDBOX_WATCHDOG_FAILED"):
            await check_watchdog(client, TOKEN)


@pytest.mark.parametrize(
    "status,body,headers",
    [
        (302, b"", {"Location": "https://example.invalid/"}),
        (401, b"", {}),
        (200, b"x" * 4097, {}),
        (200, b"{}", {"Content-Encoding": "identity"}),
    ],
)
async def test_controller_rejects_failure_redirect_and_oversized_health(status, body, headers):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(status, content=body, headers=headers)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ResearchRejected):
            await check_watchdog(client, TOKEN)
    assert len(seen) == 1
    assert str(seen[0].url) == "http://sandbox-watchdog:8093/health"


async def test_production_controller_uses_injected_watchdog_and_closes_lock(monkeypatch, tmp_path):
    import radar.sandbox_controller as controller

    checked = AsyncMock()
    lock = BytesIO()
    monkeypatch.setattr(controller, "acquire_lock", lambda _: lock)

    class Health:
        failed = False

        def __init__(self, commands, executor, *, watchdog):
            assert watchdog is checked

        async def startup(self):
            await checked()

        async def monitor(self):
            await asyncio.Event().wait()

    monkeypatch.setattr(controller, "SandboxHealth", Health)
    app = controller.production_app(
        "sha256:" + "a" * 64, TOKEN, tmp_path / "lock", watchdog=checked
    )
    async with app.router.lifespan_context(app):
        checked.assert_awaited_once()
        assert not lock.closed
    assert lock.closed
