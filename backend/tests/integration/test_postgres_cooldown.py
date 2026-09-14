from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.ingest_repository import IngestRepository
from radar.models import IngestJobRow, SourceRow

pytestmark = pytest.mark.postgres


def _source(*, cooled: bool) -> SourceRow:
    return SourceRow(
        id=uuid4(),
        name=f"cooldown-source-{uuid4()}",
        feed_url=f"https://example.com/{uuid4()}/feed",
        enabled=True,
        health="rate_limited" if cooled else "healthy",
        consecutive_failures=0,
        canonical_host="example.com",
        channel_type="rss",
        cooldown_until=(datetime.now(UTC) + timedelta(minutes=5)) if cooled else None,
    )


@pytest.mark.asyncio
async def test_rate_limited_source_is_skipped_until_its_persisted_cooldown_expires(
    postgres_database: Any,
) -> None:
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = IngestRepository(sessions)
    cooled = _source(cooled=True)
    available = _source(cooled=False)
    try:
        async with sessions() as session, session.begin():
            session.add_all([cooled, available])
        run, _ = await repository.create_run([cooled.id, available.id], f"cooldown:{uuid4()}")

        first = await repository.claim("worker-first")
        assert first is not None and first.source_id == available.id
        assert await repository.finish(first.id, "worker-first", first.lease_generation, True)
        assert await repository.claim("worker-blocked") is None

        past = datetime.now(UTC) - timedelta(seconds=1)
        async with sessions() as session, session.begin():
            await session.execute(
                update(SourceRow).where(SourceRow.id == cooled.id).values(cooldown_until=past)
            )
        released = await repository.claim("worker-released")
        assert released is not None and released.source_id == cooled.id
        before_finish = datetime.now(UTC)
        assert await repository.finish(
            released.id,
            "worker-released",
            released.lease_generation,
            False,
            "upstream returned 429",
            retry_after_seconds=120,
        )

        async with sessions() as session:
            stored_source = await session.get(SourceRow, cooled.id)
            stored_job = await session.get(IngestJobRow, released.id)
            assert stored_source is not None
            assert stored_source.health == "rate_limited"
            assert stored_source.cooldown_until is not None
            assert stored_source.cooldown_until >= before_finish + timedelta(seconds=119)
            assert stored_job is not None and stored_job.state == "retry_wait"
            assert stored_job.not_before == stored_source.cooldown_until

        assert await repository.claim("worker-still-blocked") is None
        async with sessions() as session, session.begin():
            await session.execute(
                update(SourceRow).where(SourceRow.id == cooled.id).values(cooldown_until=past)
            )
            await session.execute(
                update(IngestJobRow).where(IngestJobRow.id == released.id).values(not_before=past)
            )
        retried = await repository.claim("worker-after-cooldown")
        assert retried is not None and retried.id == released.id
        assert retried.lease_generation == released.lease_generation + 1
        assert await repository.finish(
            retried.id, "worker-after-cooldown", retried.lease_generation, True
        )
        assert run.id == retried.run_id
    finally:
        await engine.dispose()
