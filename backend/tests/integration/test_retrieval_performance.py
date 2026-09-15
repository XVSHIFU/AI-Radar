import asyncio
import math
import os
from time import perf_counter
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from radar.postgres_repository import PostgresRepository
from radar.schemas import Filters

pytestmark = [pytest.mark.postgres, pytest.mark.performance]
CONCURRENCY = 20
STEADY_ROUNDS = 5


def _p95(samples: list[float]) -> float:
    return sorted(samples)[math.ceil(len(samples) * 0.95) - 1]


async def _warm_pool(engine: AsyncEngine) -> None:
    gate = asyncio.Event()
    ready = 0

    async def hold_connection() -> None:
        nonlocal ready
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            ready += 1
            if ready == CONCURRENCY:
                gate.set()
            await gate.wait()

    await asyncio.gather(*(hold_connection() for _ in range(CONCURRENCY)))


def test_event_list_and_keyword_p95(migration_database: Any) -> None:
    if os.environ.get("RADAR_RUN_PERFORMANCE_TESTS") != "1":
        pytest.skip("set RADAR_RUN_PERFORMANCE_TESTS=1 for the benchmark")
    event_count = int(os.environ.get("RADAR_PERFORMANCE_EVENT_COUNT", "10000"))
    migration_database.upgrade()

    async def run() -> dict[str, float | int]:
        connection = await migration_database.connect()
        try:
            await connection.execute(
                """INSERT INTO events (
                    id, title_zh, summary_zh, category, importance, event_date,
                    date_precision, status, source_count, evidence_count, content_version,
                    search_document, search_config_version, search_indexed_at
                ) SELECT md5(i::text)::uuid, '人工智能模型 ' || i, '性能基线 ' || i,
                    'research', 3, DATE '2026-09-01' + (i % 10), 'day', 'published',
                    1, 0, 1, '人工 工智 智能 模型 性能 基线 ' || i, 'cjk-bigram-v1', now()
                FROM generate_series(1, $1) AS i""",
                event_count,
            )
        finally:
            await connection.close()

        async def measure(call: Any) -> float:
            started = perf_counter()
            await call()
            return perf_counter() - started

        cold_engine = create_async_engine(migration_database.rendered_url, pool_size=CONCURRENCY)
        cold_repository = PostgresRepository(
            async_sessionmaker(cold_engine, expire_on_commit=False), "benchmark-secret-is-long"
        )
        try:
            cold_samples = await asyncio.gather(
                *(
                    measure(
                        lambda: cold_repository.list_events(Filters(category="research"), 20, None)
                    )
                    for _ in range(CONCURRENCY)
                )
            )
        finally:
            await cold_engine.dispose()

        warm_engine = create_async_engine(migration_database.rendered_url, pool_size=CONCURRENCY)
        warm_repository = PostgresRepository(
            async_sessionmaker(warm_engine, expire_on_commit=False), "benchmark-secret-is-long"
        )
        await _warm_pool(warm_engine)
        warm_filters = Filters(category="research", min_importance=3)
        try:
            warm_snapshot_samples = await asyncio.gather(
                *(
                    measure(lambda: warm_repository.list_events(warm_filters, 20, None))
                    for _ in range(CONCURRENCY)
                )
            )
            steady_samples: list[float] = []
            for _ in range(STEADY_ROUNDS):
                steady_samples.extend(
                    await asyncio.gather(
                        *(
                            measure(lambda: warm_repository.list_events(warm_filters, 20, None))
                            for _ in range(CONCURRENCY)
                        )
                    )
                )
            keyword_samples: list[float] = []
            for _ in range(STEADY_ROUNDS):
                keyword_samples.extend(
                    await asyncio.gather(
                        *(
                            measure(
                                lambda: warm_repository.search_events(
                                    Filters(q="人工智能", category="research"), 20
                                )
                            )
                            for _ in range(CONCURRENCY)
                        )
                    )
                )
            if os.environ.get("RADAR_EXPLAIN_SNAPSHOT_PAGE") == "1":
                explain_connection = await migration_database.connect()
                try:
                    plan = await explain_connection.fetch(
                        """EXPLAIN (ANALYZE, BUFFERS)
                        SELECT entry.value FROM retrieval_snapshots s
                        CROSS JOIN LATERAL jsonb_array_elements(
                          jsonb_path_query_array(
                            s.items, '$[$lo to $hi]',
                            jsonb_build_object('lo', 5000, 'hi', 5019)
                          )
                        ) WITH ORDINALITY AS entry(value, ordinal)
                        WHERE s.id=(SELECT id FROM retrieval_snapshots LIMIT 1)
                        ORDER BY entry.ordinal"""
                    )
                    print({"snapshot_page_explain": [row[0] for row in plan]})
                finally:
                    await explain_connection.close()
        finally:
            await warm_engine.dispose()
        return {
            "events": event_count,
            "concurrency": CONCURRENCY,
            "cold_snapshot_samples": len(cold_samples),
            "cold_snapshot_p95_seconds": _p95(list(cold_samples)),
            "warm_pool_cold_snapshot_samples": len(warm_snapshot_samples),
            "warm_pool_cold_snapshot_p95_seconds": _p95(list(warm_snapshot_samples)),
            "steady_snapshot_samples": len(steady_samples),
            "steady_snapshot_p95_seconds": _p95(steady_samples),
            "warm_keyword_samples": len(keyword_samples),
            "warm_keyword_p95_seconds": _p95(keyword_samples),
        }

    print(asyncio.run(run()))
