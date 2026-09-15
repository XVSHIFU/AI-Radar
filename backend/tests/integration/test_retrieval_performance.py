import asyncio
import os
from time import perf_counter
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.postgres_repository import PostgresRepository
from radar.schemas import Filters

pytestmark = [pytest.mark.postgres, pytest.mark.performance]


def test_ten_thousand_event_list_and_keyword_p95(migration_database: Any) -> None:
    if os.environ.get("RADAR_RUN_PERFORMANCE_TESTS") != "1":
        pytest.skip("set RADAR_RUN_PERFORMANCE_TESTS=1 for the 10k benchmark")
    migration_database.upgrade()

    async def run() -> tuple[float, float]:
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
                FROM generate_series(1, 10000) AS i"""
            )
        finally:
            await connection.close()
        engine = create_async_engine(migration_database.rendered_url, pool_size=20)
        repository = PostgresRepository(
            async_sessionmaker(engine, expire_on_commit=False), "benchmark-secret-is-long"
        )

        async def measure(call: Any) -> float:
            started = perf_counter()
            await call()
            return perf_counter() - started

        try:
            list_times = await asyncio.gather(
                *(
                    measure(lambda: repository.list_events(Filters(category="research"), 20, None))
                    for _ in range(20)
                )
            )
            search_times = await asyncio.gather(
                *(
                    measure(
                        lambda: repository.search_events(
                            Filters(q="人工智能", category="research"), 20
                        )
                    )
                    for _ in range(20)
                )
            )
        finally:
            await engine.dispose()
        return sorted(list_times)[18], sorted(search_times)[18]

    list_p95, search_p95 = asyncio.run(run())
    print(
        {
            "events": 10000,
            "concurrency": 20,
            "list_p95_seconds": list_p95,
            "keyword_p95_seconds": search_p95,
        }
    )
