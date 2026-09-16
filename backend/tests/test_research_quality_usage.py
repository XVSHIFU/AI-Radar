from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from test_research_quality_seed import DATABASE, load

usage = load("research_quality_usage")


def call(**changes):
    return {
        "id": uuid4(),
        "status": "completed",
        "attempt": 1,
        "provider": "fixture",
        "model_id": "fixture",
        "prompt_tokens": 10,
        "completion_tokens": 3,
        "finished_at": datetime.now(UTC),
        **changes,
    }


def test_unknown_model_usage_never_becomes_reserved_or_estimated_tokens():
    report = usage.summarize([call(), call(prompt_tokens=None)])
    assert report["metrics"] == {"model_calls": 2, "input_tokens": None, "output_tokens": 6}
    assert report["known_partial_tokens"]["input_tokens"] == 10
    report = usage.summarize([call(status="pending", finished_at=None)])
    assert report["status"] == "unsettled"
    assert all(value is None for value in report["metrics"].values())


def test_actual_zero_and_recorded_retry_remain_distinct():
    assert usage.summarize([])["metrics"] == {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    assert usage.summarize([call(attempt=2)])["recorded_retry_attempts"] == 1
    with pytest.raises(ValueError):
        usage.summarize([call(prompt_tokens=True)])


async def test_lookup_rejects_business_database_without_any_query():
    connection = AsyncMock()
    with pytest.raises(ValueError):
        await usage.read_usage(connection, "ai_radar", "a" * 64, "q1", variant="agent")
    connection.fetchval.assert_not_awaited()


@pytest.mark.parametrize("variant", ["agent", "legacy"])
async def test_lookup_is_read_only_owner_bound_and_never_reads_quota_reservations(variant):
    parent = {"id": uuid4(), "status": "finished", "settled_at": datetime.now(UTC)}
    connection = MagicMock()
    connection.transaction.return_value = AsyncMock()
    connection.fetchval = AsyncMock(return_value=DATABASE)
    connection.fetchrow = AsyncMock(return_value=parent)
    connection.fetch = AsyncMock(return_value=[call()])
    report = await usage.read_usage(connection, DATABASE, "a" * 64, "q1", variant=variant)
    assert report["metrics"]["input_tokens"] == 10
    connection.transaction.assert_called_once_with(isolation="repeatable_read", readonly=True)
    assert connection.fetchrow.call_args.args[1:] == ("a" * 64, "q1")
    assert "input_charge" not in connection.fetch.call_args.args[0]
    assert "output_charge" not in connection.fetch.call_args.args[0]
    if variant == "legacy":
        assert connection.fetch.call_args.args[1] == f"answer:pub-{parent['id'].hex}"
    else:
        assert connection.fetch.call_args.args[1] == parent["id"]
