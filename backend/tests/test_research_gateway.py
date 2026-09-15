import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from test_research_stream import Chunks, client_for, event

from radar.research_gateway import ResearchSession
from radar.research_guard import ResearchGuard, ResearchRejected


class Executor:
    def __init__(self):
        self.seen = []

    async def execute(self, name, arguments):
        self.seen.append((name, arguments))
        return {"total": 17, "scope": "frozen-on-server"}


class Ledger:
    def __init__(self):
        self.claimed = []
        self.settled = []

    async def claim(self, run_id, lease):
        self.claimed.append((run_id, lease))

    async def settle(self, run_id, lease, usage, status):
        self.settled.append((run_id, lease, usage, status))


def setup(blocks, seen=None):
    guard = ResearchGuard(uuid4(), "a" * 64, datetime.now(UTC) + timedelta(seconds=90))
    executor, ledger = Executor(), Ledger()
    session = ResearchSession(
        guard=guard,
        system="server-only-system",
        prompt="server-admitted-question",
        provider=client_for(Chunks(blocks), seen),
        executor=executor,
        ledger=ledger,
    )
    return session, guard.capability, executor, ledger


def tool_blocks(name="aggregate_events", args=None, call_id="call-1"):
    return [
        event(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(
                                {"dimension": "category"} if args is None else args
                            ),
                        },
                    }
                ]
            },
            "tool_calls",
        ),
        b"data: [DONE]\n\n",
    ]


async def test_provider_history_and_tool_results_only_come_from_trusted_gateway():
    seen = []
    session, capability, executor, ledger = setup(tool_blocks(), seen)
    try:
        parts = [item async for item in session.model(capability, 1, 1000)]
        assert parts[-1] == {"type": "finish", "reason": "toolUse"}
        request = seen[0][1]
        assert request["messages"] == [
            {"role": "system", "content": "server-only-system"},
            {"role": "user", "content": "server-admitted-question"},
        ]
        assert {tool["function"]["name"] for tool in request["tools"]} == {
            "resolve_entities",
            "search_events",
            "get_event_evidence",
            "aggregate_events",
            "compare_periods",
            "build_chart",
            "load_research_skill",
        }
        with pytest.raises(ResearchRejected, match="INVALID_TOOL_CALL"):
            await session.tool(
                capability,
                "aggregate_events",
                {"dimension": "category", "scope_id": "other"},
                "call-1",
            )
        assert executor.seen == []
        result = await session.tool(
            capability, "aggregate_events", {"dimension": "category"}, "call-1"
        )
        assert result["total"] == 17
        assert len(executor.seen) == 1 and len(ledger.claimed) == len(ledger.settled) == 1
        assert ledger.settled[0][2] is None  # Unknown usage is never invented as zero.
        with pytest.raises(ResearchRejected):
            await session.tool(capability, "aggregate_events", {"dimension": "category"}, "call-1")
    finally:
        await session.provider.close()


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("shell", {"command": "id"}),
        ("search_events", {"scope_id": "other"}),
        ("get_event_evidence", {"event_ids": ["not-a-uuid"]}),
        (
            "compare_periods",
            {
                "first": {"from": "2026-02-31", "to": "2026-03-01"},
                "second": {"from": "2026-03-01", "to": "2026-03-02"},
            },
        ),
    ],
)
async def test_invalid_provider_calls_are_consumed_without_execution_or_next_turn_deadlock(
    name, args
):
    seen = []
    session, capability, executor, _ = setup(tool_blocks(name, args), seen)
    try:
        _ = [item async for item in session.model(capability, 1, 1000)]
        # This fixture repeats the invalid tool call; the assertion concerns readiness
        # for a second paid turn and the gateway-owned error already in its transcript.
        _ = [item async for item in session.model(capability, 2, 1000)]
        assert len(seen) == 2 and executor.seen == []
        messages = seen[1][1]["messages"]
        assert messages[-1]["role"] == "tool"
        assert json.loads(messages[-1]["content"])["error"]["code"] in {
            "INVALID_ARGUMENT",
            "TOOL_UNAVAILABLE",
        }
    finally:
        await session.provider.close()


async def test_unfinished_valid_tool_prevents_next_paid_model_call():
    seen = []
    session, capability, _, ledger = setup(tool_blocks(), seen)
    try:
        _ = [item async for item in session.model(capability, 1, 1000)]
        with pytest.raises(ResearchRejected, match="RUN_BUSY"):
            _ = [item async for item in session.model(capability, 2, 1000)]
        assert len(seen) == 1 and len(ledger.claimed) == 1
    finally:
        await session.provider.close()


async def test_disconnect_settles_unknown_usage_and_revokes_capability():
    session, capability, _, ledger = setup(
        [
            event({"content": "draft"}),
            event({}, "stop"),
            b"data: [DONE]\n\n",
        ]
    )
    stream = session.model(capability, 1, 1000)
    try:
        assert (await anext(stream))["text"] == "draft"
        await stream.aclose()
        assert ledger.settled[0][2] is None and ledger.settled[0][3] == "cancelled"
        with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
            session.guard.check(capability)
    finally:
        await session.provider.close()


async def test_persistent_admission_failure_never_reaches_provider():
    seen = []
    session, capability, _, ledger = setup(tool_blocks(), seen)

    async def reject(run_id, lease):
        raise ResearchRejected("BUDGET_EXCEEDED")

    ledger.claim = reject
    try:
        with pytest.raises(ResearchRejected, match="BUDGET_EXCEEDED"):
            _ = [item async for item in session.model(capability, 1, 1000)]
        assert seen == [] and ledger.settled == []
        with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
            session.guard.check(capability)
    finally:
        await session.provider.close()


async def test_failed_persistent_settlement_revokes_tools_before_another_round():
    session, capability, executor, ledger = setup(tool_blocks())

    async def fail_settlement(run_id, lease, usage, status):
        raise RuntimeError("test-ledger-unavailable")

    ledger.settle = fail_settlement
    try:
        with pytest.raises(RuntimeError, match="test-ledger-unavailable"):
            _ = [item async for item in session.model(capability, 1, 1000)]
        with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
            await session.tool(capability, "aggregate_events", {"dimension": "category"}, "call-1")
        assert executor.seen == []
    finally:
        await session.provider.close()


async def test_active_stream_excludes_concurrent_paid_turn():
    seen = []
    session, capability, _, ledger = setup(
        [
            event({"content": "draft"}),
            event({}, "stop"),
            b"data: [DONE]\n\n",
        ],
        seen,
    )
    stream = session.model(capability, 1, 1000)
    try:
        await anext(stream)
        with pytest.raises(ResearchRejected, match="RUN_BUSY"):
            _ = [item async for item in session.model(capability, 2, 1000)]
        assert len(seen) == len(ledger.claimed) == 1
    finally:
        await stream.aclose()
        await session.provider.close()


async def test_reused_provider_call_id_still_settles_second_paid_call():
    session, capability, _, ledger = setup(tool_blocks())
    try:
        _ = [item async for item in session.model(capability, 1, 1000)]
        await session.tool(capability, "aggregate_events", {"dimension": "category"}, "call-1")
        with pytest.raises(ResearchRejected, match="INVALID_TOOL_CALL"):
            _ = [item async for item in session.model(capability, 2, 1000)]
        assert len(ledger.claimed) == len(ledger.settled) == 2
        assert ledger.settled[-1][-1] == "failed"
        with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
            session.guard.check(capability)
    finally:
        await session.provider.close()
