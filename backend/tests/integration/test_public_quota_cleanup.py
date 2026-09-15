import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from test_public_quota import key, ledger  # noqa: F401

from radar.deepseek_client import ProviderUsage
from radar.models import LlmCallRow
from radar.public_quota import PublicAdmissionError, PublicAskRow
from radar.public_quota_cleanup import clean_public_quota
from radar.research_guard import ModelLease
from radar.research_ledger import PostgresResearchLedger, ResearchCallRow

pytestmark = pytest.mark.postgres


async def age(quota, reservation, delta):
    async with quota.sessions() as session, session.begin():
        now = await session.scalar(select(func.clock_timestamp()))
        await session.execute(
            update(PublicAskRow)
            .where(PublicAskRow.id == reservation.id)
            .values(admitted_at=now - delta, active_until=now - delta + timedelta(seconds=90))
        )


async def test_ip_forgetting_preserves_live_quota_and_owner_bound_replay(ledger):  # noqa: F811
    owner, ip = key("owner"), key("ip")
    fresh = await ledger.reserve(owner, ip, "fresh", key("fresh"))
    await ledger.settle(fresh.id, owner, started=True, input_tokens=10, output_tokens=5)
    old = await ledger.reserve(owner, ip, "old", key("old"))
    await ledger.settle(old.id, owner, started=True, input_tokens=10, output_tokens=5)
    await age(ledger, old, timedelta(hours=49))
    result = await clean_public_quota(ledger.sessions)
    assert result.forgotten_ips == 1 and result.deleted_requests == 0
    async with ledger.sessions() as session:
        assert (await session.get(PublicAskRow, old.id)).ip_hash is None
        assert (await session.get(PublicAskRow, fresh.id)).ip_hash == ip
    assert (await ledger.snapshot(ip)).remaining == 19
    with pytest.raises(PublicAdmissionError, match="IDEMPOTENCY_REPLAY"):
        await ledger.reserve(owner, key("changed IP"), "old", key("old"))
    assert (await clean_public_quota(ledger.sessions)).forgotten_ips == 0


async def test_expired_idempotency_links_are_deleted_but_model_usage_survives(ledger):  # noqa: F811
    owner = key("owner")
    reservation = await ledger.reserve(owner, key("ip"), "old", key("payload"))
    calls = PostgresResearchLedger(ledger.sessions, owner, provider="fixture", model="test")
    lease = ModelLease(1, 1000, 500)
    await calls.claim(reservation.id, lease)
    await calls.settle(reservation.id, lease, ProviderUsage(50, 20, 70), "completed")
    async with ledger.sessions() as session:
        call_id = await session.scalar(
            select(ResearchCallRow.model_call_id).where(ResearchCallRow.run_id == reservation.id)
        )
    await ledger.settle(reservation.id, owner, started=True, input_tokens=50, output_tokens=20)
    await age(ledger, reservation, timedelta(days=32))
    result = await clean_public_quota(ledger.sessions)
    assert result.deleted_requests == 1
    async with ledger.sessions() as session:
        assert await session.get(PublicAskRow, reservation.id) is None
        assert (
            await session.scalar(
                select(ResearchCallRow).where(ResearchCallRow.run_id == reservation.id)
            )
            is None
        )
        usage = await session.get(LlmCallRow, call_id)
        assert (usage.prompt_tokens, usage.completion_tokens) == (50, 20)


async def test_cleanup_skips_locked_rows_and_honors_batch_limit(ledger):  # noqa: F811
    owner = key("owner")
    records = []
    for i in range(3):
        reservation = await ledger.reserve(owner, key("ip"), str(i), key(str(i)))
        await ledger.settle(reservation.id, owner, started=True)
        await age(ledger, reservation, timedelta(days=3))
        records.append(reservation)
    async with ledger.sessions() as session, session.begin():
        await session.scalar(
            select(PublicAskRow).where(PublicAskRow.id == records[0].id).with_for_update()
        )
        result = await asyncio.wait_for(
            clean_public_quota(ledger.sessions, batch_size=1), timeout=2
        )
        assert result.forgotten_ips == 1
        assert (await session.get(PublicAskRow, records[0].id)).ip_hash is not None
    assert (await clean_public_quota(ledger.sessions)).forgotten_ips == 2
    with pytest.raises(ValueError):
        await clean_public_quota(ledger.sessions, batch_size=True)


def test_retention_migration_rollback_preserves_forgotten_row_and_charges(migration_database):
    migration_database.upgrade()
    row_id = uuid4()

    async def seed():
        connection = await migration_database.connect()
        try:
            await connection.execute(
                "INSERT INTO public_ask_requests "
                "(id,owner_hash,client_request_id,payload_hash,ip_hash,admitted_at,active_until,"
                "charged,status,input_charge,output_charge) VALUES ($1,$2,'retained',$2,NULL,"
                "now()-interval '3 days',now()-interval '3 days',true,'finished',100,50)",
                row_id,
                "a" * 64,
            )
        finally:
            await connection.close()

    asyncio.run(seed())
    migration_database.downgrade("0012_research_model_calls")
    migration_database.upgrade()

    async def verify():
        connection = await migration_database.connect()
        try:
            row = await connection.fetchrow(
                "SELECT ip_hash, owner_hash, input_charge, output_charge "
                "FROM public_ask_requests WHERE id=$1",
                row_id,
            )
            assert tuple(row) == ("", "a" * 64, 100, 50)
        finally:
            await connection.close()

    asyncio.run(verify())
