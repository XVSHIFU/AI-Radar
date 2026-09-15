import asyncio
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.public_quota import PostgresPublicQuota, PublicAdmissionError, PublicAskRow, QuotaPolicy

pytestmark = pytest.mark.postgres


def key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture
async def ledger(postgres_database):
    engine = create_async_engine(postgres_database.rendered_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    # This fixture owns only the new table in the disposable database.
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM public_ask_requests"))
    policy = QuotaPolicy(input_per_day=10_000_000, output_per_day=10_000_000)
    yield PostgresPublicQuota(sessions, policy)
    await engine.dispose()


async def test_twenty_questions_are_persistent_and_followups_count(ledger):
    ip = key("same NAT")
    for i in range(20):
        row = await ledger.reserve(key(f"user-{i}"), ip, f"followup-{i}", key("payload"))
        await ledger.settle(row.id, key(f"user-{i}"), started=True, input_tokens=5, output_tokens=2)
    restarted = PostgresPublicQuota(ledger.sessions, ledger.policy)
    with pytest.raises(PublicAdmissionError) as rejected:
        await restarted.reserve(key("new browser"), ip, "new-question", key("payload"))
    assert rejected.value.code == "ASK_QUOTA_EXCEEDED"
    assert rejected.value.retry_after > 172_700
    assert (await restarted.snapshot(ip)).remaining == 0
    assert (await restarted.snapshot(key("other IP"))).remaining == 20


async def test_last_slot_is_shared_across_sessions_and_process_instances(ledger):
    ip = key("ip")
    policy = QuotaPolicy(questions=1, input_per_day=10_000_000, output_per_day=10_000_000)
    a = PostgresPublicQuota(ledger.sessions, policy)
    b = PostgresPublicQuota(ledger.sessions, policy)
    results = await asyncio.gather(
        a.reserve(key("owner-a"), ip, "request-a", key("a")),
        b.reserve(key("owner-b"), ip, "request-b", key("b")),
        return_exceptions=True,
    )
    assert sum(isinstance(x, PublicAdmissionError) for x in results) == 1
    error = next(x for x in results if isinstance(x, PublicAdmissionError))
    assert error.code == "ASK_QUOTA_EXCEEDED"
    assert (await a.snapshot(ip)).remaining == 0


async def test_replay_and_conflict_are_owner_bound_and_do_not_recharge(ledger):
    owner, ip = key("owner"), key("ip")
    row = await ledger.reserve(owner, ip, "same-request", key("first"))
    await ledger.settle(row.id, owner, started=True, input_tokens=3, output_tokens=2)
    for payload, code in [("first", "IDEMPOTENCY_REPLAY"), ("changed", "IDEMPOTENCY_KEY_CONFLICT")]:
        with pytest.raises(PublicAdmissionError) as rejected:
            await ledger.reserve(owner, key("new ip"), "same-request", key(payload))
        assert rejected.value.code == code
    with pytest.raises(PublicAdmissionError) as rejected:
        await ledger.settle(row.id, key("other owner"), started=False)
    assert rejected.value.code == "RUN_NOT_FOUND"
    assert (await ledger.snapshot(ip)).remaining == 19
    # Same identifier in a different anonymous session is a separate question, not a read.
    other = await ledger.reserve(key("other owner"), ip, "same-request", key("first"))
    assert other.id != row.id and other.quota.remaining == 18


async def test_rolling_window_and_preflight_rejection(ledger):
    owner, ip = key("owner"), key("ip")
    row = await ledger.reserve(owner, ip, "old", key("a"))
    async with ledger.sessions() as session, session.begin():
        await session.execute(
            text(
                "UPDATE public_ask_requests "
                "SET admitted_at = clock_timestamp() - interval '48 hours', "
                "active_until = clock_timestamp() - interval '1 hour' WHERE id=:id"
            ),
            {"id": row.id},
        )
    assert (await ledger.snapshot(ip)).remaining == 20
    rejected = await ledger.reserve(owner, ip, "preflight", key("b"))
    await ledger.settle(rejected.id, owner, started=False)
    assert (await ledger.snapshot(ip)).remaining == 20
    with pytest.raises(PublicAdmissionError) as replay:
        await ledger.reserve(owner, ip, "preflight", key("b"))
    assert replay.value.code == "IDEMPOTENCY_REPLAY"


async def test_global_budget_retains_unknown_usage_and_releases_known_unused(ledger):
    policy = QuotaPolicy(input_per_day=24_000, output_per_day=4_800)
    constrained = PostgresPublicQuota(ledger.sessions, policy)
    owner = key("owner")
    first = await constrained.reserve(owner, key("ip"), "first", key("payload"))
    await constrained.settle(first.id, owner, started=True)
    with pytest.raises(PublicAdmissionError) as rejected:
        await constrained.reserve(owner, key("other ip"), "second", key("payload"))
    assert rejected.value.code == "ASK_DAILY_BUDGET_EXCEEDED"
    async with ledger.sessions() as session:
        persisted = await session.get(PublicAskRow, first.id)
        assert persisted.input_charge == 24_000 and persisted.output_charge == 4_800
    # Settlement is immutable: a replay cannot turn unknown consumed work into zero.
    await constrained.settle(first.id, owner, started=False)
    assert (await constrained.snapshot(key("ip"))).remaining == 19


async def test_concurrency_reservation_and_known_zero_settlement(ledger):
    owner = key("owner")
    rows = [await ledger.reserve(owner, key(str(i)), str(i), key("p")) for i in range(2)]
    with pytest.raises(PublicAdmissionError) as rejected:
        await ledger.reserve(owner, key("third"), "third", key("p"))
    assert rejected.value.code == "ASK_BUSY"
    await ledger.settle(rows[0].id, owner, started=True, input_tokens=0, output_tokens=0)
    await ledger.reserve(owner, key("third"), "third", key("p"))
    async with ledger.sessions() as session:
        row = await session.scalar(select(PublicAskRow).where(PublicAskRow.id == rows[0].id))
        assert row.input_charge == row.output_charge == 0
    with pytest.raises(PublicAdmissionError):
        await ledger.settle(uuid4(), owner, started=False)


async def test_both_http_endpoints_share_quota_and_owner_bound_replay(ledger, client, monkeypatch):
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock

    import httpx

    from radar.main import app
    from radar.public_identity import PublicIdentity
    from radar.qa_limits import AskAdmission

    app.state.settings = app.state.settings.model_copy(update={"radar_data_mode": "postgres"})
    app.state.sessions = ledger.sessions
    app.state.public_identity = PublicIdentity("integration-secret-for-quota-123456789")
    app.state.public_quota = ledger
    app.state.ask_admission = AskAdmission(per_client=100, total_per_minute=100)
    result = {
        "request_id": "empty",
        "query_plan_public": {},
        "data_mode": "postgres",
        "as_of": datetime.now(UTC),
        "filters_applied": {},
        "answer_status": "no_answer",
        "scope_total": 0,
        "retrieved_count": 0,
        "summarized_count": 0,
        "citation_count": 0,
        "coverage": "complete",
    }
    normal = AsyncMock(return_value=result)
    streaming = AsyncMock(return_value=result)
    monkeypatch.setattr("radar.main.answer_question", normal)
    monkeypatch.setattr("radar.main.prepare_stream", streaming)
    transport = httpx.ASGITransport(app=app, client=("192.0.2.4", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        assert (await http.get("/api/v1/assistant/session")).status_code == 200
        for i in range(20):
            path = "/api/v1/ask" + ("/stream" if i % 2 else "")
            response = await http.post(path, json={"question": "总结", "client_request_id": str(i)})
            assert response.status_code == 200, response.text
        replay = await http.post(
            "/api/v1/ask/stream", json={"question": "总结", "client_request_id": "0"}
        )
        assert replay.status_code == 409 and replay.json()["code"] == "IDEMPOTENCY_REPLAY"
        # Creating a fresh anonymous owner keeps the same IP's exhausted allowance.
        http.cookies.clear()
        app.state.public_quota = PostgresPublicQuota(ledger.sessions, ledger.policy)
        snapshot = await http.get("/api/v1/assistant/session")
        assert snapshot.json()["quota"]["remaining"] == 0
        denied = await http.post(
            "/api/v1/ask",
            json={"question": "追问", "client_request_id": "21"},
            headers={"x-forwarded-for": "203.0.113.8"},
        )
        assert denied.status_code == 429 and denied.headers["retry-after"]
        assert normal.await_count == 10 and streaming.await_count == 10


async def test_controller_settles_usage_and_keeps_cancelled_unknown_charge(ledger):
    from radar.deepseek_client import Completion, ProviderUsage
    from radar.public_assistant import PublicRun
    from radar.qa_service import QaService
    from radar.schemas import AskRequest

    owner, ip = key("owner"), key("ip")
    usage_ledger = QaService(ledger.sessions, None)
    for suffix, completion, expected in [
        (
            "known",
            Completion("answer", "test", ProviderUsage(prompt_tokens=11, completion_tokens=7)),
            (11, 7),
        ),
        ("cancelled", None, (24_000, 4_800)),
    ]:
        reservation = await ledger.reserve(owner, ip, suffix, key(suffix))
        payload = AskRequest(question="总结", client_request_id=f"pub-{reservation.id.hex}")
        call_id = await usage_ledger.claim(payload.client_request_id, key(suffix))
        await usage_ledger.mark(call_id, "completed" if completion else "unknown", completion, None)
        await PublicRun(ledger, owner, reservation, payload).finish(completed=bool(completion))
        async with ledger.sessions() as session:
            row = await session.get(PublicAskRow, reservation.id)
            assert row.charged and (row.input_charge, row.output_charge) == expected
    assert (await ledger.snapshot(ip)).remaining == 18
