"""Real snapshot import/concurrent-write checks in the existing disposable DB."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.public_quota import PostgresPublicQuota, QuotaPolicy
from radar.recovery_bundle import InvalidBundle
from radar.recovery_snapshot import capture_snapshot, verify_restored_snapshot

pytestmark = pytest.mark.postgres


async def test_snapshot_is_stable_across_new_question_and_restore_gate_detects_it(
    postgres_database,
):
    engine = create_async_engine(postgres_database.rendered_url)
    quota = PostgresPublicQuota(
        async_sessionmaker(engine),
        QuotaPolicy(input_per_day=10000000, output_per_day=10000000),
    )
    try:
        async with capture_snapshot(engine) as before:
            initial = before["fingerprints"]["public_ask_requests"]["rows"]
            await quota.reserve(uuid4().hex * 2, uuid4().hex * 2, uuid4().hex, "a" * 64)
            # The import is exactly the mechanism used by pg_dump --snapshot.
            async with engine.connect() as imported:
                await imported.execution_options(isolation_level="REPEATABLE READ")
                async with imported.begin():
                    await imported.execute(text("SET TRANSACTION READ ONLY"))
                    await imported.execute(
                        text("SET TRANSACTION SNAPSHOT '" + before["snapshot_id"] + "'")
                    )
                    count = await imported.scalar(
                        text("SELECT count(*) FROM public.public_ask_requests")
                    )
                    assert count == initial
                    assert await imported.scalar(text("SHOW transaction_read_only")) == "on"
            with pytest.raises(InvalidBundle, match="public_ask_requests"):
                await verify_restored_snapshot(engine, before["fingerprints"])
        async with capture_snapshot(engine) as after:
            assert after["fingerprints"]["public_ask_requests"]["rows"] == initial + 1
            await verify_restored_snapshot(engine, after["fingerprints"])
    finally:
        await engine.dispose()
