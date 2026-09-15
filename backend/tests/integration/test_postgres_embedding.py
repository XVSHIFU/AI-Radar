import asyncio
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.embedding_indexer import EmbeddingIndexer
from radar.local_bge import LocalBgeM3Provider
from radar.postgres_repository import PostgresRepository
from radar.schemas import Filters

pytestmark = [pytest.mark.postgres, pytest.mark.embedding]


def test_real_local_embedding_profile_index_and_semantic_search(migration_database: Any) -> None:
    if os.environ.get("RADAR_RUN_EMBEDDING_TESTS") != "1":
        pytest.skip("set RADAR_RUN_EMBEDDING_TESTS=1 with the pinned model cache")
    model_dir = Path(os.environ["RADAR_TEST_BGE_MODEL_DIR"])
    revision = os.environ["RADAR_TEST_BGE_REVISION"]
    migration_database.upgrade()

    async def run() -> None:
        connection = await migration_database.connect()
        try:
            for title, summary in (
                ("DeepSeek 推理模型", "面向复杂任务的模型发布"),
                ("多语言向量模型", "支持中文语义检索"),
            ):
                await connection.execute(
                    "INSERT INTO events (id,title_zh,summary_zh,category,importance,event_date,"
                    "date_precision,status,source_count,evidence_count,content_version) "
                    "VALUES ($1,$2,$3,'research',3,$4,'day','published',1,0,1)",
                    uuid4(),
                    title,
                    summary,
                    date(2026, 9, 15),
                )
        finally:
            await connection.close()
        engine = create_async_engine(migration_database.rendered_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        provider = LocalBgeM3Provider(model_dir, revision, threads=4)
        try:
            indexed = await EmbeddingIndexer(sessions, provider).run(limit=10, activate=True)
            assert indexed.indexed == 2
            assert indexed.activated is True
            result = await PostgresRepository(
                sessions, "embedding-test-secret", embedding_provider=provider
            ).search_events(Filters(q="中文检索", category="research"), 10)
            assert result.scope_total == 2
            assert result.semantic_count == 2
            assert result.embedding_profile == provider.profile.fingerprint
            assert result.degraded_reason is None
        finally:
            await engine.dispose()

    asyncio.run(run())
