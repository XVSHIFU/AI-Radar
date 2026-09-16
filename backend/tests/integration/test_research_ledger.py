import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.deepseek_client import ProviderUsage
from radar.public_quota import PostgresPublicQuota, PublicAskRow, QuotaPolicy
from radar.research_guard import ModelLease, ResearchRejected
from radar.research_ledger import PostgresResearchLedger, finish_public_question, research_usage

pytestmark = pytest.mark.postgres


@pytest.fixture
async def account(postgres_database):
    engine = create_async_engine(postgres_database.rendered_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, ip = uuid4().hex * 2, uuid4().hex * 2
    quota = PostgresPublicQuota(
        sessions, QuotaPolicy(input_per_day=10000000, output_per_day=10000000)
    )
    reservation = await quota.reserve(owner, ip, uuid4().hex, "a" * 64)
    ledger = PostgresResearchLedger(sessions, owner, provider="test", model="fixture")
    try:
        yield sessions, owner, ip, quota, reservation, ledger
    finally:
        await quota.settle(reservation.id, owner, started=True)
        await engine.dispose()


async def test_three_call_totals_persist_and_unknown_usage_keeps_its_reservation(account):
    sessions, owner, ip, quota, run, ledger = account
    for sequence, usage in enumerate(
        (ProviderUsage(1000, 200, 1200), None, ProviderUsage(2000, 600, 2600)), start=1
    ):
        lease = ModelLease(sequence, 6000, 2000)
        await ledger.claim(run.id, lease)
        await ledger.settle(run.id, lease, usage, "completed")
        ledger = PostgresResearchLedger(sessions, owner, provider="test", model="fixture")
    async with sessions() as session:
        assert await research_usage(session, run.id) == (3, 9000, 2800)
    await finish_public_question(sessions, run.id, owner, "not-a-legacy-call", completed=True)
    async with sessions() as session:
        row = await session.get(PublicAskRow, run.id)
        assert row.input_charge == 9000 and row.output_charge == 2800 and row.charged
    assert (await quota.snapshot(ip)).remaining == 4
    with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
        await ledger.claim(run.id, ModelLease(3, 10, 10))


async def test_concurrent_duplicate_claims_and_wrong_owner_never_double_admit(account):
    sessions, owner, _, _, run, ledger = account
    lease = ModelLease(1, 6000, 2000)
    results = await asyncio.gather(
        ledger.claim(run.id, lease), ledger.claim(run.id, lease), return_exceptions=True
    )
    assert sum(result is None for result in results) == 1
    assert any(isinstance(result, ResearchRejected) for result in results)
    restarted = PostgresResearchLedger(sessions, owner, provider="test", model="fixture")
    with pytest.raises(ResearchRejected, match="RUN_BUSY"):
        await restarted.claim(run.id, ModelLease(2, 1000, 1000))
    stranger = PostgresResearchLedger(sessions, "b" * 64, provider="test", model="fixture")
    with pytest.raises(ResearchRejected, match="RUN_NOT_FOUND"):
        await stranger.settle(run.id, lease, ProviderUsage(0, 0, 0), "completed")
    await ledger.settle(run.id, lease, None, "cancelled")
    await ledger.settle(run.id, lease, ProviderUsage(0, 0, 0), "completed")
    async with sessions() as session:
        assert await research_usage(session, run.id) == (1, 6000, 2000)


async def test_persistent_aggregate_budget_blocks_third_expensive_call_and_fourth_call(account):
    _, _, _, _, run, ledger = account
    for sequence in (1, 2):
        lease = ModelLease(sequence, 10000, 2000)
        await ledger.claim(run.id, lease)
        await ledger.settle(run.id, lease, None, "completed")
    with pytest.raises(ResearchRejected, match="BUDGET_EXCEEDED"):
        await ledger.claim(run.id, ModelLease(3, 5000, 1000))
    with pytest.raises(ResearchRejected, match="BUDGET_EXCEEDED"):
        await ledger.claim(run.id, ModelLease(4, 10, 10))


async def test_question_finalization_race_cannot_release_an_admitted_call(account):
    sessions, owner, _, _, run, ledger = account
    result = await asyncio.gather(
        ledger.claim(run.id, ModelLease(1, 6000, 2000)),
        finish_public_question(sessions, run.id, owner, "unused", completed=False),
        return_exceptions=True,
    )
    async with sessions() as session:
        row = await session.scalar(select(PublicAskRow).where(PublicAskRow.id == run.id))
        count, inputs, outputs = await research_usage(session, run.id)
        assert row.input_charge == inputs and row.output_charge == outputs
        assert row.charged == (count > 0)
    if result[0] is not None:
        assert isinstance(result[0], ResearchRejected) and count == 0


async def test_cancelled_question_keeps_pending_reservation_after_late_usage_settlement(account):
    sessions, owner, _, _, run, ledger = account
    lease = ModelLease(1, 6000, 2000)
    await ledger.claim(run.id, lease)
    await finish_public_question(sessions, run.id, owner, "unused", completed=False)
    await ledger.settle(run.id, lease, ProviderUsage(100, 20, 120), "cancelled")
    await finish_public_question(sessions, run.id, owner, "unused", completed=True)
    async with sessions() as session:
        row = await session.get(PublicAskRow, run.id)
        assert row.input_charge == 6000 and row.output_charge == 2000 and row.charged
