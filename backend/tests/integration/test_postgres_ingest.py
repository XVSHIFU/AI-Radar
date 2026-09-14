import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.ingest_repository import BudgetUnavailable, IngestRepository
from radar.models import BudgetReservationRow, IngestJobRow, IngestRunRow, SourceRow

pytestmark = pytest.mark.postgres


async def _repository(database: Any):
    engine = create_async_engine(database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return engine, sessions, IngestRepository(sessions)


async def _add_sources(sessions: Any, count: int) -> list[SourceRow]:
    sources = [
        SourceRow(
            id=uuid4(),
            name=f"source-{uuid4()}",
            feed_url=f"https://example.com/{uuid4()}/feed",
            enabled=True,
            health="healthy",
            consecutive_failures=0,
            canonical_host="example.com",
            channel_type="rss",
        )
        for _ in range(count)
    ]
    async with sessions() as session, session.begin():
        session.add_all(sources)
    return sources


@pytest.mark.asyncio
async def test_concurrent_idempotency_and_claims_do_not_duplicate_work(
    postgres_database: Any,
) -> None:
    engine, sessions, repository = await _repository(postgres_database)
    try:
        sources = await _add_sources(sessions, 2)
        key = f"integration:{uuid4()}"
        results = await asyncio.gather(
            repository.create_run([source.id for source in sources], key),
            repository.create_run([source.id for source in sources], key),
        )

        assert len({result[0].id for result in results}) == 1
        assert sorted(result[1] for result in results) == [False, True]
        run_id = results[0][0].id
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count()).select_from(IngestRunRow).where(IngestRunRow.id == run_id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(IngestJobRow)
                    .where(IngestJobRow.run_id == run_id)
                )
                == 2
            )

        claims = await asyncio.gather(*(repository.claim(f"worker-{index}") for index in range(4)))
        claimed = [job for job in claims if job is not None]
        assert len(claimed) == 2
        assert len({job.id for job in claimed}) == 2
        for job in claimed:
            assert await repository.finish(job.id, str(job.lease_owner), job.lease_generation, True)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_lease_is_fenced_and_final_expiry_fails_the_run(
    postgres_database: Any,
) -> None:
    engine, sessions, repository = await _repository(postgres_database)
    try:
        source = (await _add_sources(sessions, 1))[0]
        run, _ = await repository.create_run([source.id], f"lease:{uuid4()}")
        first = await repository.claim("worker-first", lease_seconds=60)
        assert first is not None
        async with sessions() as session, session.begin():
            await session.execute(
                update(IngestJobRow)
                .where(IngestJobRow.id == first.id)
                .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
            )

        second = await repository.claim("worker-second", lease_seconds=60)
        assert second is not None
        assert second.id == first.id
        assert second.lease_generation == first.lease_generation + 1
        assert not await repository.heartbeat(first.id, "worker-first", first.lease_generation)
        assert not await repository.finish(first.id, "worker-first", first.lease_generation, True)

        async with sessions() as session, session.begin():
            await session.execute(
                update(IngestJobRow)
                .where(IngestJobRow.id == second.id)
                .values(
                    attempts=IngestJobRow.max_attempts,
                    lease_until=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
        assert await repository.claim("worker-third") is None
        async with sessions() as session:
            job = await session.get(IngestJobRow, second.id)
            stored_run = await session.get(IngestRunRow, run.id)
            assert job is not None and job.state == "failed"
            assert job.last_error == "lease expired after final attempt"
            assert stored_run is not None and stored_run.status == "failed"
            assert stored_run.finished_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_budget_reservation_is_idempotent_and_serialized(
    postgres_database: Any,
) -> None:
    engine, sessions, repository = await _repository(postgres_database)
    try:
        scope = f"daily:{uuid4()}"
        request_id = f"request:{uuid4()}"
        first = await repository.reserve_budget(
            scope, request_id, Decimal("4.00"), Decimal("10.00")
        )
        repeated = await repository.reserve_budget(
            scope, request_id, Decimal("4.00"), Decimal("10.00")
        )
        assert repeated.id == first.id

        contenders = await asyncio.gather(
            repository.reserve_budget(
                scope, f"request:{uuid4()}", Decimal("6.00"), Decimal("10.00")
            ),
            repository.reserve_budget(
                scope, f"request:{uuid4()}", Decimal("6.00"), Decimal("10.00")
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(item, BudgetReservationRow) for item in contenders) == 1
        assert sum(isinstance(item, BudgetUnavailable) for item in contenders) == 1
        async with sessions() as session:
            reserved = await session.scalar(
                select(func.sum(BudgetReservationRow.amount)).where(
                    BudgetReservationRow.scope == scope
                )
            )
        assert reserved == Decimal("10.000000")
    finally:
        await engine.dispose()
