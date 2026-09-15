import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.deepseek_client import Completion, DeepSeekClient, ProviderUsage
from radar.event_merge_service import EventMergeService
from radar.extraction_schemas import ExtractionResult
from radar.extraction_service import ExtractionService

pytestmark = pytest.mark.postgres


def _extraction(title: str, quote: str) -> ExtractionResult:
    return ExtractionResult.model_validate(
        {
            "relevant": True,
            "title_zh": title,
            "summary_zh": "一家机构发布了新的人工智能模型。",
            "category": "model_release",
            "importance": 4,
            "entities": [
                {
                    "canonical_name": "Concurrency AI",
                    "entity_type": "company",
                    "role": "subject",
                }
            ],
            "evidence": [{"paragraph_id": "p-1", "quote_text": quote}],
        }
    )


async def _seed_version(
    database: Any,
    *,
    article_id: UUID | None = None,
    fetched_at: datetime,
    quote: str,
) -> tuple[UUID, UUID]:
    source_id, run_id, version_id = uuid4(), uuid4(), uuid4()
    article_id = article_id or uuid4()
    url = f"https://example.com/{version_id}"
    connection = await database.connect()
    try:
        await connection.execute(
            "INSERT INTO sources "
            "(id,name,feed_url,enabled,health,consecutive_failures,canonical_host,channel_type) "
            "VALUES ($1,$2,$3,true,'healthy',0,'example.com','rss')",
            source_id,
            f"concurrency-{source_id}",
            f"https://example.com/{source_id}.xml",
        )
        exists = await connection.fetchval("SELECT 1 FROM articles WHERE id=$1", article_id)
        if not exists:
            await connection.execute(
                "INSERT INTO articles (id,source_id,canonical_url) VALUES ($1,$2,$3)",
                article_id,
                source_id,
                f"https://example.com/article/{article_id}",
            )
        await connection.execute(
            "INSERT INTO article_versions "
            "(id,article_id,title,source_url,paragraphs,content_hash,fetched_at) "
            "VALUES ($1,$2,'Frozen title',$3,$4::jsonb,$5,$6)",
            version_id,
            article_id,
            url,
            json.dumps({"p-1": quote}),
            uuid4().hex + uuid4().hex,
            fetched_at,
        )
        await connection.execute(
            "INSERT INTO ingest_runs (id,idempotency_key,payload_hash,trigger_type,status) "
            "VALUES ($1,$2,$3,'manual','completed')",
            run_id,
            f"concurrency-run-{run_id}",
            uuid4().hex + uuid4().hex,
        )
        await connection.execute(
            "INSERT INTO article_candidates "
            "(id,run_id,source_id,article_version_id,canonical_url,original_url,title,status) "
            "VALUES ($1,$2,$3,$4,$5,$5,'Candidate','needs_review')",
            uuid4(),
            run_id,
            source_id,
            version_id,
            url,
        )
    finally:
        await connection.close()
    return article_id, version_id


async def _publish(
    service: ExtractionService,
    version_id: UUID,
    title: str,
    quote: str,
) -> bool:
    call_id = await service._claim(version_id)
    assert call_id is not None
    version = await service._version(version_id)
    return await service._publish(
        call_id,
        version,
        date(2026, 9, 15),
        _extraction(title, quote),
        Completion("{}", f"response-{version_id}", ProviderUsage(10, 5, 15)),
    )


@pytest.mark.asyncio
async def test_publish_merge_and_unmerge_serialize_without_losing_relations(
    postgres_database: Any,
) -> None:
    started = datetime(2026, 9, 15, tzinfo=UTC)
    first_quote = "Concurrency AI released the first model."
    article_id, first_version = await _seed_version(
        postgres_database,
        fetched_at=started,
        quote=first_quote,
    )
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = ExtractionService(sessions, cast(DeepSeekClient, None))
    merges = EventMergeService(sessions)
    try:
        assert await _publish(service, first_version, "首次发布", first_quote)
        connection = await postgres_database.connect()
        try:
            source_id = await connection.fetchval(
                "SELECT event_id FROM event_articles WHERE article_id=$1", article_id
            )
            target_id = uuid4()
            await connection.execute(
                "INSERT INTO events "
                "(id,title_zh,summary_zh,category,importance,event_date,date_precision,"
                "date_basis,status,source_count,evidence_count,content_version) "
                "VALUES ($1,'保留事件','摘要','model_release',4,NULL,'unknown','unknown',"
                "'published',0,0,1)",
                target_id,
            )
        finally:
            await connection.close()

        second_quote = "Concurrency AI released the second model."
        _, second_version = await _seed_version(
            postgres_database,
            article_id=article_id,
            fetched_at=started + timedelta(seconds=1),
            quote=second_quote,
        )
        published, merge_id = await asyncio.wait_for(
            asyncio.gather(
                _publish(service, second_version, "第二次发布", second_quote),
                merges.merge(
                    source_id,
                    target_id,
                    reason="concurrency regression",
                    evidence={"case": "publish-vs-merge"},
                    operator="test",
                ),
            ),
            timeout=10,
        )
        assert published is True

        connection = await postgres_database.connect()
        try:
            canonical = await connection.fetchrow(
                "SELECT source_count,evidence_count FROM events WHERE id=$1", target_id
            )
            assert dict(canonical) == {"source_count": 2, "evidence_count": 2}
        finally:
            await connection.close()

        third_quote = "Concurrency AI released the third model."
        _, third_version = await _seed_version(
            postgres_database,
            article_id=article_id,
            fetched_at=started + timedelta(seconds=2),
            quote=third_quote,
        )
        published, _ = await asyncio.wait_for(
            asyncio.gather(
                _publish(service, third_version, "第三次发布", third_quote),
                merges.unmerge(merge_id, operator="test"),
            ),
            timeout=10,
        )
        assert published is True

        connection = await postgres_database.connect()
        try:
            source = await connection.fetchrow("SELECT * FROM events WHERE id=$1", source_id)
            target = await connection.fetchrow("SELECT * FROM events WHERE id=$1", target_id)
            relation_count = await connection.fetchval(
                "SELECT count(*) FROM event_articles WHERE event_id=$1 AND article_id=$2",
                source_id,
                article_id,
            )
            evidence_count = await connection.fetchval(
                "SELECT count(*) FROM evidence WHERE event_id=$1", source_id
            )
            log = await connection.fetchrow("SELECT * FROM event_merge_log WHERE id=$1", merge_id)
            assert source["status"] == "published"
            assert source["merged_into_event_id"] is None
            assert source["source_count"] == 3
            assert source["evidence_count"] == 3
            assert target["source_count"] == 0
            assert target["evidence_count"] == 0
            assert relation_count == 1
            assert evidence_count == 3
            assert log["reverted_at"] is not None
            assert log["reverted_by"] == "test"
        finally:
            await connection.close()
    finally:
        await engine.dispose()
