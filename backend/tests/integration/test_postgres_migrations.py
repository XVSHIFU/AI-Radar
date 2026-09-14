import asyncio
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.postgres


async def _revision_and_vector(database: Any) -> tuple[str, bool]:
    connection = await database.connect()
    try:
        revision = await connection.fetchval("SELECT version_num FROM alembic_version")
        vector = await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        return str(revision), bool(vector)
    finally:
        await connection.close()


def test_schema_can_upgrade_downgrade_and_reupgrade(
    migration_database: Any,
) -> None:
    migration_database.upgrade()
    assert asyncio.run(_revision_and_vector(migration_database)) == (
        "0004_candidate_versions",
        True,
    )

    source_id = uuid4()
    run_id = uuid4()
    job_id = uuid4()

    async def seed() -> None:
        connection = await migration_database.connect()
        try:
            await connection.execute(
                "INSERT INTO sources (id, name, feed_url, enabled, health, "
                "consecutive_failures, canonical_host, channel_type) "
                "VALUES ($1, $2, $3, true, 'healthy', 0, $4, 'rss')",
                source_id,
                "migration-source",
                "https://example.com/feed",
                "example.com",
            )
            await connection.execute(
                "INSERT INTO ingest_runs (id, idempotency_key, payload_hash, trigger_type) "
                "VALUES ($1, $2, $3, 'manual')",
                run_id,
                "migration-run",
                "hash",
            )
            await connection.execute(
                "INSERT INTO ingest_jobs "
                "(id, run_id, source_id, job_key, stage, payload, state) "
                "VALUES ($1, $2, $3, $4, 'feed_discovery', '{}'::jsonb, 'succeeded')",
                job_id,
                run_id,
                source_id,
                f"source:{run_id}:{source_id}",
            )
        finally:
            await connection.close()

    asyncio.run(seed())
    migration_database.downgrade("0002_ingest_pipeline")
    migration_database.upgrade()

    async def verify_preserved_rows() -> tuple[int, int, int]:
        connection = await migration_database.connect()
        try:
            return (
                await connection.fetchval("SELECT count(*) FROM sources WHERE id = $1", source_id),
                await connection.fetchval("SELECT count(*) FROM ingest_runs WHERE id = $1", run_id),
                await connection.fetchval("SELECT count(*) FROM ingest_jobs WHERE id = $1", job_id),
            )
        finally:
            await connection.close()

    assert asyncio.run(verify_preserved_rows()) == (1, 1, 1)
    assert asyncio.run(_revision_and_vector(migration_database)) == (
        "0004_candidate_versions",
        True,
    )
