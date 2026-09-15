import asyncio
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.embedding_indexer import EmbeddingIndexer
from radar.retrieval import EmbeddingProfile

pytestmark = pytest.mark.postgres


def test_incremental_batches_and_version_race(migration_database: Any) -> None:
    migration_database.upgrade()

    async def run() -> None:
        engine = create_async_engine(migration_database.rendered_url)
        sessions = async_sessionmaker(engine)  # Default expiration must also work in CLI.
        ids = [uuid4() for _ in range(3)]
        async with engine.begin() as conn:
            for index, event_id in enumerate(ids):
                await conn.execute(
                    text(
                        "INSERT INTO events "
                        "(id,title_zh,summary_zh,category,importance,date_precision,"
                        "date_basis,status,source_count,evidence_count,content_version) "
                        "VALUES "
                        "(:id,:title,'summary','research',3,'unknown','unknown','published',0,"
                        "0,1)"
                    ),
                    {"id": event_id, "title": f"Model {index}"},
                )

        class Provider:
            profile = EmbeddingProfile("test", "incremental", "v1", 1024, True, "plain-test")
            mutate = False

            async def embed_query(self, value: str) -> list[float]:
                if self.mutate and value != "dimension probe":
                    self.mutate = False
                    async with engine.begin() as conn:
                        await conn.execute(
                            text(
                                "UPDATE events SET title_zh='changed while computing', "
                                "content_version=content_version+1 WHERE id=:id"
                            ),
                            {"id": ids[0]},
                        )
                return [1.0] + [0.0] * 1023

        provider = Provider()
        indexer = EmbeddingIndexer(sessions, provider)
        try:
            batches = [await indexer.run(limit=1) for _ in range(3)]
            assert [batch.indexed for batch in batches] == [1, 1, 1]
            assert len({batch.profile_id for batch in batches}) == 1
            assert (await indexer.run(limit=1, activate=True)).indexed == 0
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE events SET summary_zh='revised',content_version=content_version+1 "
                        "WHERE id=:id"
                    ),
                    {"id": ids[0]},
                )
                stale = (
                    await conn.execute(
                        text(
                            "SELECT status,embedding IS NULL AS cleared FROM event_embeddings_v1 "
                            "WHERE event_id=:id"
                        ),
                        {"id": ids[0]},
                    )
                ).one()
                assert stale.status == "stale" and stale.cleared
            provider.mutate = True
            raced = await indexer.run(limit=1)
            assert raced.indexed == 0 and raced.skipped == 1
            async with engine.connect() as conn:
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM event_embeddings_v1 WHERE status='ready' "
                            "AND event_id=:id"
                        ),
                        {"id": ids[0]},
                    )
                    == 0
                )
            repaired = await indexer.run(limit=1, activate=True)
            assert repaired.indexed == 1 and repaired.activated
            async with engine.connect() as conn:
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM event_embeddings_v1 ee JOIN events e ON "
                            "e.id=ee.event_id "
                            "WHERE ee.status='ready' AND ee.event_content_version=e.content_version"
                        )
                    )
                    == 3
                )
        finally:
            await engine.dispose()

    asyncio.run(run())
