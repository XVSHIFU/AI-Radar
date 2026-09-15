from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from radar.research_guard import RequestedTool, ResearchGuard, ResearchRejected, RunCapabilities


def guard():
    return ResearchGuard(uuid4(), "a" * 64, datetime.now(UTC) + timedelta(seconds=90))


async def test_model_reservations_are_sequenced_serial_and_bounded():
    run = guard()
    for sequence in range(1, 4):
        lease = await run.reserve_model(run.capability, sequence, {"messages": []}, 2000)
        with pytest.raises(ResearchRejected, match="RUN_BUSY"):
            await run.reserve_model(run.capability, sequence + 1, {}, 1)
        assert lease.output_reserved == (800 if sequence == 3 else 2000)
        await run.settle_model(run.capability, lease, input_tokens=None, output_tokens=None)
        with pytest.raises(ResearchRejected, match="IDEMPOTENCY_REPLAY"):
            await run.settle_model(run.capability, lease, input_tokens=0, output_tokens=0)
    assert run.output_charge == 4800
    with pytest.raises(ResearchRejected, match="BUDGET_EXCEEDED"):
        await run.reserve_model(run.capability, 4, {}, 1)


async def test_full_unicode_request_budget_is_checked_before_model_admission():
    run = guard()
    with pytest.raises(ResearchRejected, match="BUDGET_EXCEEDED"):
        await run.reserve_model(run.capability, 1, {"instructions": "中" * 8000}, 1600)
    assert run.model_calls == 0 and run.input_charge == 0


async def test_only_provider_requested_tools_with_unchanged_arguments_are_authorized():
    run = guard()
    args = {"dimension": "category"}
    lease = await run.reserve_model(run.capability, 1, {}, 100)
    await run.settle_model(
        run.capability,
        lease,
        input_tokens=5,
        output_tokens=4,
        requested_tools={"one": RequestedTool("aggregate_events", args)},
    )
    args["dimension"] = "date"
    with pytest.raises(ResearchRejected, match="INVALID_TOOL_CALL"):
        await run.begin_tool(run.capability, "one", "aggregate_events", args)
    with pytest.raises(ResearchRejected, match="INVALID_TOOL_CALL"):
        await run.begin_tool(run.capability, "not-requested", "aggregate_events", {})
    await run.begin_tool(run.capability, "one", "aggregate_events", {"dimension": "category"})
    with pytest.raises(ResearchRejected, match="RUN_BUSY"):
        await run.reserve_model(run.capability, 2, {}, 100)
    await run.finish_tool("one")
    with pytest.raises(ResearchRejected, match="IDEMPOTENCY_REPLAY"):
        await run.begin_tool(run.capability, "one", "aggregate_events", {"dimension": "category"})
    assert run.input_charge == 5 and run.output_charge == 4


async def test_tool_budget_is_independent_of_pi_and_shell_never_gets_authorized():
    run = guard()
    lease = await run.reserve_model(run.capability, 1, {}, 100)
    calls = {str(i): RequestedTool("search_events", {}) for i in range(5)}
    calls["shell"] = RequestedTool("shell", {"command": "whoami"})
    await run.settle_model(
        run.capability, lease, input_tokens=1, output_tokens=1, requested_tools=calls
    )
    for i in range(4):
        await run.begin_tool(run.capability, str(i), "search_events", {})
        await run.finish_tool(str(i))
    with pytest.raises(ResearchRejected, match="BUDGET_EXCEEDED"):
        await run.begin_tool(run.capability, "4", "search_events", {})
    with pytest.raises(ResearchRejected, match="TOOL_UNAVAILABLE"):
        await run.begin_tool(run.capability, "shell", "shell", {"command": "whoami"})
    assert run.business_calls == 4


async def test_revocation_allows_accounting_but_not_more_work():
    run = guard()
    lease = await run.reserve_model(run.capability, 1, {}, 1600)
    run.close()
    await run.settle_model(run.capability, lease, input_tokens=12, output_tokens=5)
    assert run.input_charge == 12 and run.output_charge == 5
    with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
        await run.reserve_model(run.capability, 2, {}, 1600)


def test_capabilities_are_random_bound_to_run_and_disappear_after_restart():
    directory = RunCapabilities()
    first, second = guard(), guard()
    directory.add(first)
    directory.add(second)
    assert first.capability != second.capability
    assert directory.get(first.capability).run_id == first.run_id
    with pytest.raises(ResearchRejected, match="RUN_BUSY"):
        directory.add(guard())
    for invalid in ["another-user", "非法", first.capability + "x"]:
        with pytest.raises(ResearchRejected, match="RUN_NOT_FOUND"):
            directory.get(invalid)
    directory.remove(first)
    with pytest.raises(ResearchRejected, match="RUN_NOT_FOUND"):
        directory.get(first.capability)
    with pytest.raises(ResearchRejected, match="RUN_NOT_FOUND"):
        RunCapabilities().get(second.capability)
