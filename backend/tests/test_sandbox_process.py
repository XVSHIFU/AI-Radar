import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_executor import DockerCommands


def fake_process(stdout=b"", stderr=b"", *, hanging=False):
    process = SimpleNamespace(
        stdin=SimpleNamespace(write=Mock(), drain=AsyncMock(), close=Mock()),
        stdout=asyncio.StreamReader(),
        stderr=asyncio.StreamReader(),
        returncode=None,
    )
    process.stdout.feed_data(stdout)
    process.stderr.feed_data(stderr)
    if not hanging:
        process.stdout.feed_eof()
        process.stderr.feed_eof()

    def kill():
        process.returncode = -9

    async def wait():
        if process.returncode is None:
            process.returncode = 0
        return process.returncode

    process.kill = Mock(side_effect=kill)
    process.wait = AsyncMock(side_effect=wait)
    return process


async def test_controller_uses_fixed_binary_socket_and_clean_environment(monkeypatch):
    process = fake_process(b"ok")
    create = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    result = await DockerCommands().execute(["version"], payload=b"input")
    assert result.code == 0 and result.stdout == b"ok"
    assert create.await_args.args == (
        "/usr/bin/docker",
        "--host=unix:///run/docker.sock",
        "version",
    )
    assert create.await_args.kwargs["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    process.stdin.write.assert_called_once_with(b"input")
    process.stdin.close.assert_called_once()


@pytest.mark.parametrize(
    "stdout,stderr", [(b"x" * 11, b""), (b"", b"x" * 65537)], ids=["stdout", "stderr"]
)
async def test_both_output_streams_bounded_and_cli_killed(monkeypatch, stdout, stderr):
    process = fake_process(stdout, stderr)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(ResearchRejected, match="RESOURCE_LIMIT"):
        await DockerCommands().execute(["start"], output_limit=10)
    process.kill.assert_called_once()
    process.wait.assert_awaited()


async def test_hanging_cli_is_killed_on_deadline(monkeypatch):
    process = fake_process(hanging=True)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(TimeoutError):
        await DockerCommands().execute(["start"], timeout=0.01)
    process.kill.assert_called_once()
    process.wait.assert_awaited()
