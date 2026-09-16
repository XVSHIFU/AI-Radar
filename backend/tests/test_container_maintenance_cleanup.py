import asyncio
import signal

import pytest

from radar import container_maintenance


async def test_repeated_cancellation_cannot_interrupt_pending_spawn_cleanup(monkeypatch):
    spawning, release_spawn, cleaning, release_cleanup = (asyncio.Event() for _ in range(4))
    child = object()
    cleaned = []

    async def spawn(*args, **kwargs):
        spawning.set()
        await release_spawn.wait()
        return child

    async def cleanup(process):
        cleaning.set()
        await release_cleanup.wait()
        cleaned.append(process)

    monkeypatch.setattr(container_maintenance.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(container_maintenance, "terminate", cleanup)
    task = asyncio.create_task(container_maintenance.execute(["fixed"], asyncio.Event(), 1))
    await spawning.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release_spawn.set()
    await cleaning.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release_cleanup.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned == [child]


async def test_remaining_group_is_killed_even_after_direct_child_exits(monkeypatch):
    sent = []
    monkeypatch.setattr(
        container_maintenance.os, "killpg", lambda pid, sig: sent.append((pid, sig)), raising=False
    )
    monkeypatch.setattr(signal, "SIGKILL", getattr(signal, "SIGKILL", 9), raising=False)

    class Process:
        pid = 12345
        returncode = 0

        async def wait(self):
            return 0

    await container_maintenance.terminate(Process())
    assert sent == [(12345, signal.SIGTERM), (12345, signal.SIGKILL)]
