import copy
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_executor import CommandResult
from radar.sandbox_reaper import expired_owned, reap_expired

NOW = datetime(2026, 9, 16, 12, tzinfo=UTC)


def container(age=31):
    return {
        "Config": {"Labels": {"ai-radar.sandbox": "task"}, "User": "65532:65532"},
        "Name": "/radar-python-" + "a" * 32,
        "Created": (NOW - timedelta(seconds=age)).isoformat(),
        "HostConfig": {
            "Runtime": "runsc",
            "NetworkMode": "none",
            "Privileged": False,
            "ReadonlyRootfs": True,
        },
    }


def test_only_expired_owned_sandboxes_selected():
    assert expired_owned(container(), NOW)
    assert expired_owned(container(30), NOW)
    assert not expired_owned(container(29), NOW)
    assert not expired_owned(container(-1), NOW)
    for name in ["/postgres", "/radar-python-other", "/radar-python-" + "a" * 31]:
        record = container()
        record["Name"] = name
        assert not expired_owned(record, NOW)
    record = container()
    record["Config"]["Labels"] = {}
    assert not expired_owned(record, NOW)


@pytest.mark.parametrize(
    "field,value",
    [("Runtime", "runc"), ("NetworkMode", "host"), ("Privileged", True), ("ReadonlyRootfs", False)],
)
def test_inconsistent_owned_configuration_rejected(field, value):
    record = container()
    record["HostConfig"][field] = value
    with pytest.raises(ResearchRejected, match="SANDBOX_WATCHDOG_FAILED"):
        expired_owned(record, NOW)


async def test_remove_expired_preserve_fresh_and_unrelated():
    old, fresh, unrelated = container(), container(1), copy.deepcopy(container())
    unrelated["Name"] = "/database"
    commands = AsyncMock()
    commands.execute.side_effect = [
        CommandResult(0, b"aaaaaaaaaaaa\nbbbbbbbbbbbb\ncccccccccccc\n"),
        CommandResult(0, json.dumps([old]).encode()),
        CommandResult(0, b"removed"),
        CommandResult(0, json.dumps([fresh]).encode()),
        CommandResult(0, json.dumps([unrelated]).encode()),
    ]
    assert await reap_expired(commands, now=NOW) == {"checked": 3, "removed": 1}
    removals = [
        call.args[0] for call in commands.execute.await_args_list if call.args[0][0] == "rm"
    ]
    assert removals == [["rm", "--force", "--volumes", "aaaaaaaaaaaa"]]


async def test_racing_request_cleanup_is_safe():
    commands = AsyncMock()
    commands.execute.side_effect = [
        CommandResult(0, b"aaaaaaaaaaaa\n"),
        CommandResult(1, b"[]"),
        CommandResult(0, b""),
    ]
    assert await reap_expired(commands, now=NOW) == {"checked": 0, "removed": 0}
    assert not any(call.args[0][0] == "rm" for call in commands.execute.await_args_list)


async def test_removal_failure_not_silently_accepted():
    commands = AsyncMock()
    commands.execute.side_effect = [
        CommandResult(0, b"aaaaaaaaaaaa\n"),
        CommandResult(0, json.dumps([container()]).encode()),
        CommandResult(1, b""),
        CommandResult(0, b"aaaaaaaaaaaa\n"),
    ]
    with pytest.raises(ResearchRejected, match="SANDBOX_WATCHDOG_FAILED"):
        await reap_expired(commands, now=NOW)


@pytest.mark.parametrize("raw", [b"--privileged", b"bad-container", b"a" * 65])
async def test_unexpected_docker_ids_never_used(raw):
    commands = AsyncMock()
    commands.execute.return_value = CommandResult(0, raw)
    with pytest.raises(ResearchRejected, match="SANDBOX_WATCHDOG_FAILED"):
        await reap_expired(commands, now=NOW)
    assert commands.execute.await_count == 1
