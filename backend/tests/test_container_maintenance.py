import asyncio
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from radar import container_entry, container_maintenance, container_model
from radar.container_maintenance import MaintenanceHalted, job_command, supervise

DATES = {"RADAR_HISTORY_FROM": "2026-08-01", "RADAR_HISTORY_TO": "2026-09-30"}
ROOT = Path(__file__).resolve().parents[2]


def test_date_window_preserves_old_clamp_and_does_not_fetch_future_dates():
    assert job_command("history-discover", DATES, date(2026, 7, 31)) is None
    current = job_command("history-discover", DATES, date(2026, 9, 16))
    assert current[-6:] == [
        "--date-from",
        "2026-08-01",
        "--date-to",
        "2026-09-16",
        "--max-pages",
        "40",
    ]
    ended = job_command("history-extract", DATES, date(2027, 1, 1))
    assert ended[-4:] == ["--date-to", "2026-09-30", "--limit", "80"]
    with pytest.raises(ValueError):
        job_command(
            "history-extract", {**DATES, "RADAR_HISTORY_TO": "2026-07-01"}, date(2026, 9, 16)
        )


async def test_provider_halt_never_becomes_an_automatic_paid_retry(monkeypatch):
    execution = AsyncMock(return_value=2)
    monkeypatch.setattr(container_maintenance, "execute", execution)
    with pytest.raises(MaintenanceHalted, match="maintenance_batch_stopped"):
        await supervise("history-extract", DATES, asyncio.Event(), today=lambda: date(2026, 9, 16))
    execution.assert_awaited_once()


async def test_successful_batches_are_sequential_and_recompute_the_date(monkeypatch):
    stop = asyncio.Event()
    days = iter([date(2026, 9, 16), date(2026, 9, 17)])
    seen = []

    async def execute(args, stopping, deadline):
        seen.append(args)
        if len(seen) == 2:
            stopping.set()
        return 0

    monkeypatch.setattr(container_maintenance, "execute", execute)
    monkeypatch.setitem(container_maintenance.INTERVALS, "history-discover", 0.01)
    await supervise("history-discover", DATES, stop, today=lambda: next(days))
    assert seen[0][-3] == "2026-09-16"
    assert seen[1][-3] == "2026-09-17"


class Process:
    pid = 12345

    def __init__(self):
        self.done = asyncio.Event()
        self.returncode = None

    async def wait(self):
        await self.done.wait()
        return self.returncode


@pytest.mark.parametrize("reason", ["stop", "deadline", "cancel"])
async def test_child_cleanup_finishes_before_supervisor_returns(monkeypatch, reason):
    process = Process()
    launched = asyncio.Event()
    cleaned = []

    async def spawn(*args, **kwargs):
        assert kwargs["start_new_session"] is True
        launched.set()
        return process

    async def cleanup(child):
        assert child is process
        child.returncode = -15
        child.done.set()
        cleaned.append(True)

    monkeypatch.setattr(container_maintenance.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(container_maintenance, "terminate", cleanup)
    stop = asyncio.Event()
    task = asyncio.create_task(
        container_maintenance.execute(["fixed"], stop, 0.02 if reason == "deadline" else 5)
    )
    await launched.wait()
    if reason == "stop":
        stop.set()
        assert await task is None
    elif reason == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(MaintenanceHalted, match="deadline"):
            await task
    assert cleaned == [True]
    assert process.done.is_set()


async def test_cancellation_during_spawn_does_not_orphan_the_child(monkeypatch):
    process = Process()
    spawning = asyncio.Event()
    release = asyncio.Event()
    cleaned = []

    async def spawn(*args, **kwargs):
        spawning.set()
        await release.wait()
        return process

    async def cleanup(child):
        cleaned.append(child)
        child.returncode = -15
        child.done.set()

    monkeypatch.setattr(container_maintenance.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(container_maintenance, "terminate", cleanup)
    task = asyncio.create_task(container_maintenance.execute(["fixed"], asyncio.Event(), 5))
    await spawning.wait()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned == [process]


def test_artifact_hash_gate_rejects_wrong_size_and_same_size_wrong_content(monkeypatch, tmp_path):
    # Exercise content verification here; Linux no-follow behavior is a separate gate.
    monkeypatch.setattr(os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0), raising=False)
    monkeypatch.setattr(os, "O_NONBLOCK", getattr(os, "O_NONBLOCK", 0), raising=False)
    monkeypatch.setattr(
        container_model, "ARTIFACTS", {"model.onnx": (3, hashlib.sha256(b"abc").hexdigest())}
    )
    model = tmp_path / "model.onnx"
    model.write_bytes(b"abc")
    container_model.verify_model(tmp_path)
    for content in [b"abcd", b"abd", b""]:
        model.write_bytes(content)
        with pytest.raises(ValueError, match="unverified"):
            container_model.verify_model(tmp_path)


def test_embedding_roles_reject_an_unapproved_model_path_or_revision(monkeypatch):
    monkeypatch.setattr(container_entry, "private_value", lambda _: "x" * 64)
    with pytest.raises(ValueError, match="mount"):
        container_entry.environment("embedding-index", {"EMBEDDING_MODEL_DIR": "/host"})
    with pytest.raises(ValueError, match="revision"):
        container_entry.environment(
            "api",
            {
                "EMBEDDING_MODEL_DIR": str(container_model.MODEL_ROOT),
                "EMBEDDING_MODEL_REVISION": "other",
            },
        )


def test_maintenance_profiles_keep_paid_work_opt_in_and_model_read_only():
    cfg = json.loads((ROOT / "compose.agent.json").read_text(encoding="utf-8"))
    for role in ["history-discover", "history-extract", "embedding-index", "embedding-activate"]:
        service = cfg["services"][role]
        assert service["restart"] == "no"
        assert "active" not in service["profiles"]
        assert "service_locks:/run/radar-service-locks" in service["volumes"]
        assert service["secrets"] == [{"source": "db_ingest_password", "target": "db_password"}]
    extractor = cfg["services"]["history-extract"]
    assert extractor["profiles"] == ["paid-extraction"]
    assert "model_config:/var/lib/radar-model:ro" in extractor["volumes"]
    indexer = cfg["services"]["embedding-index"]
    assert indexer["networks"] == ["database"]
    mount = [v for v in indexer["volumes"] if isinstance(v, dict)][0]
    assert mount["read_only"] is True
    assert mount["bind"]["create_host_path"] is False
    overlay = json.loads((ROOT / "compose.embedding.json").read_text(encoding="utf-8"))
    assert overlay["services"]["api"]["volumes"] == [mount]
    assert overlay["services"]["api"]["build"]["target"] == "embedding"
