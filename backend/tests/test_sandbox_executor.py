import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_executor import CommandResult, SandboxExecutor

IMAGE = "sha256:" + "a" * 64
OUTPUT = b'{"status":"completed","stdout":"3","artifacts":[]}'
DATA = [{"rows": [{"count": 3}]}]


class FakeCommands:
    def __init__(self, *, failure=None, block=False, cleanup_failure=False):
        self.calls = []
        self.failure = failure
        self.block = block
        self.cleanup_failure = cleanup_failure
        self.started = asyncio.Event()

    async def execute(self, arguments, *, payload=b"", timeout=5, output_limit=65536):
        self.calls.append((arguments, payload, timeout, output_limit))
        if arguments[0] == "rm":
            return CommandResult(int(self.cleanup_failure), b"")
        if arguments[0] == "start":
            self.started.set()
            if self.block:
                await asyncio.Event().wait()
            if self.failure:
                raise self.failure
            return CommandResult(0, OUTPUT)
        return CommandResult(0, b"container-id")


async def test_code_is_only_stdin_and_creation_has_fixed_isolation_and_limits():
    commands = FakeCommands()
    executor = SandboxExecutor(commands, IMAGE)
    code = "print('$(whoami); --privileged /run/docker.sock')"
    result = await executor.run(code, DATA)
    assert result.stdout == "3"
    create, start, remove = commands.calls
    args = create[0]
    for option in [
        "--runtime=runsc",
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
        "--restart=no",
        "--pull=never",
        "--log-driver=none",
    ]:
        assert option in args
    assert not any(a.startswith(("--volume=", "--mount=", "--env=", "--privileged")) for a in args)
    assert args[-3:] == [IMAGE, "-B", "/opt/worker.py"]
    assert code not in " ".join(args) and create[1] == b""
    assert json.loads(start[1]) == {"code": code, "datasets": DATA}
    assert start[2] == 10 and start[3] == 1572864
    assert remove[0] == ["rm", "--force", "--volumes", args[2]]


@pytest.mark.parametrize(
    "image", ["python:latest", "python:3.12", "--privileged", "sha256:" + "a" * 63]
)
def test_mutable_or_injected_image_rejected(image):
    with pytest.raises(ValueError, match="digest"):
        SandboxExecutor(FakeCommands(), image)


@pytest.mark.parametrize(
    "failure, expected",
    [(TimeoutError(), "EXECUTION_TIMEOUT"), (ResearchRejected("RESOURCE_LIMIT"), "RESOURCE_LIMIT")],
)
async def test_timeout_and_output_overflow_always_remove_container(failure, expected):
    commands = FakeCommands(failure=failure)
    executor = SandboxExecutor(commands, IMAGE)
    with pytest.raises(ResearchRejected, match=expected):
        await executor.run("print(3)", DATA)
    assert commands.calls[-1][0][0] == "rm"
    assert executor._active == 0


async def test_cancel_waits_for_removal_and_releases_slot():
    commands = FakeCommands(block=True)
    executor = SandboxExecutor(commands, IMAGE)
    task = asyncio.create_task(executor.run("print(3)", DATA))
    await commands.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert commands.calls[-1][0][0] == "rm" and executor._active == 0


async def test_third_concurrent_job_rejected_before_container_creation():
    commands = FakeCommands(block=True)
    executor = SandboxExecutor(commands, IMAGE)
    first = asyncio.create_task(executor.run("print(3)", DATA))
    await commands.started.wait()
    commands.started.clear()
    second = asyncio.create_task(executor.run("print(3)", DATA))
    await commands.started.wait()
    try:
        with pytest.raises(ResearchRejected, match="RUN_BUSY"):
            await executor.run("print(3)", DATA)
        assert len([c for c in commands.calls if c[0][0] == "create"]) == 2
    finally:
        first.cancel()
        second.cancel()
        await asyncio.gather(first, second, return_exceptions=True)
    names = [c[0][2] for c in commands.calls if c[0][0] == "create"]
    assert len(set(names)) == 2 and executor._active == 0


async def test_failed_cleanup_latches_controller_closed():
    commands = FakeCommands(cleanup_failure=True)
    executor = SandboxExecutor(commands, IMAGE)
    with pytest.raises(ResearchRejected, match="SANDBOX_CLEANUP_FAILED"):
        await executor.run("print(3)", DATA)
    count = len(commands.calls)
    with pytest.raises(ResearchRejected, match="SANDBOX_UNAVAILABLE"):
        await executor.run("print(3)", DATA)
    assert len(commands.calls) == count


async def test_uncertain_create_attempt_still_removed():
    commands = FakeCommands()
    commands.execute = AsyncMock(side_effect=[TimeoutError(), CommandResult(0, b"")])
    executor = SandboxExecutor(commands, IMAGE)
    with pytest.raises(ResearchRejected, match="EXECUTION_TIMEOUT"):
        await executor.run("print(3)", DATA)
    assert commands.execute.await_args_list[1].args[0][0] == "rm"


async def test_invalid_data_does_not_touch_docker():
    commands = FakeCommands()
    with pytest.raises(ResearchRejected, match="INVALID_ARGUMENT"):
        await SandboxExecutor(commands, IMAGE).run("print(3)", [])
    assert commands.calls == []
