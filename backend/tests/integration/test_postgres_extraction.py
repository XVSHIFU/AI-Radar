import json
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.deepseek_client import Completion, DeepSeekClient, DeepSeekError, ProviderUsage
from radar.extraction_service import ExtractionService

pytestmark = pytest.mark.postgres


class StubClient:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls = 0

    async def complete_json(self, *, system: str, user: str) -> Completion:
        assert "不得推测事件日期" in system
        assert "paragraphs" in json.loads(user)
        content = self.contents[self.calls]
        self.calls += 1
        return Completion(content, f"response-{self.calls}", ProviderUsage(10, 5, 15))


def _event_json(quote: str, *, title: str = "新模型发布") -> str:
    return json.dumps(
        {
            "relevant": True,
            "title_zh": title,
            "summary_zh": "一家机构发布了新的人工智能模型。",
            "category": "model_release",
            "importance": 4,
            "entities": [
                {
                    "canonical_name": "Example AI",
                    "entity_type": "company",
                    "role": "subject",
                }
            ],
            "evidence": [{"paragraph_id": "p-0001", "quote_text": quote}],
        },
        ensure_ascii=False,
    )


async def _seed_version(
    database: Any,
    *,
    article_id: UUID | None = None,
    sources: int = 2,
    published_at: datetime | None = datetime(2026, 8, 31, 16, 30, tzinfo=UTC),
    published_text: str | None = None,
    paragraph: str = "Example AI released a model with verified benchmarks.",
) -> tuple[UUID, UUID]:
    connection = await database.connect()
    version_id = uuid4()
    article_id = article_id or uuid4()
    run_id = uuid4()
    source_ids = [uuid4() for _ in range(sources)]
    url = f"https://example.com/{article_id}/{version_id}"
    try:
        for index, source_id in enumerate(source_ids):
            await connection.execute(
                "INSERT INTO sources "
                "(id,name,feed_url,enabled,health,consecutive_failures,"
                "canonical_host,channel_type) "
                "VALUES ($1,$2,$3,true,'healthy',0,'example.com','rss')",
                source_id,
                f"extract-{source_id}",
                f"https://example.com/{index}.xml",
            )
        if article_id is not None:
            exists = await connection.fetchval("SELECT 1 FROM articles WHERE id=$1", article_id)
            if not exists:
                await connection.execute(
                    "INSERT INTO articles (id,source_id,canonical_url) VALUES ($1,$2,$3)",
                    article_id,
                    source_ids[0],
                    f"https://example.com/article/{article_id}",
                )
        await connection.execute(
            "INSERT INTO article_versions "
            "(id,article_id,title,source_url,published_at,paragraphs,content_hash) "
            "VALUES ($1,$2,'Frozen title',$3,$4,$5::jsonb,$6)",
            version_id,
            article_id,
            url,
            published_at,
            json.dumps({"p-0001": paragraph}),
            uuid4().hex + uuid4().hex,
        )
        await connection.execute(
            "INSERT INTO ingest_runs (id,idempotency_key,payload_hash,trigger_type,status) "
            "VALUES ($1,$2,$3,'manual','completed')",
            run_id,
            f"extract-run-{run_id}",
            uuid4().hex + uuid4().hex,
        )
        for source_id in source_ids:
            await connection.execute(
                "INSERT INTO article_discoveries "
                "(id,run_id,source_id,canonical_url,original_url,title,published,article_id) "
                "VALUES ($1,$2,$3,$4,$4,'Candidate',$5,$6)",
                uuid4(),
                run_id,
                source_id,
                url,
                published_text,
                article_id,
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


@pytest.mark.asyncio
async def test_publish_idempotency_multisource_update_and_date_only(postgres_database: Any) -> None:
    article_id, first_version = await _seed_version(postgres_database)
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = StubClient([_event_json("released a model")])
    service = ExtractionService(sessions, cast(DeepSeekClient, client))
    try:
        first = await service.run(date(2026, 8, 1), date(2026, 9, 15), 10)
        repeat = await service.run(date(2026, 8, 1), date(2026, 9, 15), 10)
        assert (first.claimed, first.published, repeat.claimed, client.calls) == (1, 1, 0, 1)

        connection = await postgres_database.connect()
        try:
            event = await connection.fetchrow(
                "SELECT events.* FROM events "
                "JOIN event_articles ON event_articles.event_id=events.id "
                "WHERE event_articles.article_id=$1",
                article_id,
            )
            assert event is not None
            event_id = event["id"]
            assert event["event_date"] == date(2026, 9, 1)
            assert event["source_count"] == 2
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM article_candidates "
                    "WHERE article_version_id=$1 AND status='published'",
                    first_version,
                )
                == 2
            )
            call = await connection.fetchrow(
                "SELECT * FROM llm_calls WHERE article_version_id=$1", first_version
            )
            assert call["total_tokens"] == 15
            assert call["actual_cost"] is None
            assert call["response_content_hash"] is not None
            evidence = await connection.fetchrow(
                "SELECT * FROM evidence WHERE event_id=$1", event_id
            )
            assert evidence["verification_status"] == "unverified"
        finally:
            await connection.close()

        _, second_version = await _seed_version(
            postgres_database,
            article_id=article_id,
            sources=1,
            published_at=None,
            published_text="2026-09-15",
            paragraph="Example AI released version two with longer context.",
        )
        client.contents.append(_event_json("released version two", title="模型更新"))
        second = await service.run(date(2026, 9, 15), date(2026, 9, 15), 10)
        assert (second.claimed, second.published, client.calls) == (1, 1, 2)

        connection = await postgres_database.connect()
        try:
            event = await connection.fetchrow("SELECT * FROM events WHERE id=$1", event_id)
            assert event is not None
            assert event["content_version"] == 2
            assert event["event_date"] == date(2026, 9, 15)
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM evidence WHERE event_id=$1", event_id
                )
                == 2
            )
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM evidence WHERE article_version_id=$1", second_version
                )
                == 1
            )
        finally:
            await connection.close()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_irrelevant_and_invalid_evidence_are_not_published(postgres_database: Any) -> None:
    connection = await postgres_database.connect()
    try:
        baseline_events = await connection.fetchval("SELECT count(*) FROM events")
    finally:
        await connection.close()
    _, irrelevant_version = await _seed_version(postgres_database, sources=1)
    _, invalid_version = await _seed_version(postgres_database, sources=1)
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = StubClient(
        [
            json.dumps({"relevant": False}),
            _event_json("not in frozen paragraph"),
        ]
    )
    try:
        result = await ExtractionService(sessions, cast(DeepSeekClient, client)).run(
            date(2026, 8, 1), date(2026, 9, 15), 10
        )
        assert (result.filtered, result.failed) == (1, 1)
        connection = await postgres_database.connect()
        try:
            assert await connection.fetchval("SELECT count(*) FROM events") == baseline_events
            statuses = {
                row["article_version_id"]: row["status"]
                for row in await connection.fetch(
                    "SELECT article_version_id,status FROM article_candidates"
                )
            }
            assert statuses[irrelevant_version] == "filtered"
            assert statuses[invalid_version] == "extraction_failed"
        finally:
            await connection.close()
    finally:
        await engine.dispose()


class ErrorClient:
    def __init__(self, error: DeepSeekError) -> None:
        self.error = error
        self.calls = 0

    async def complete_json(self, *, system: str, user: str) -> Completion:
        self.calls += 1
        raise self.error


@pytest.mark.asyncio
async def test_unknown_failure_is_retained_and_not_retried(postgres_database: Any) -> None:
    _, version_id = await _seed_version(postgres_database, sources=1)
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = ErrorClient(
        DeepSeekError("timeout", code="unknown_transport_failure", stop_batch=False)
    )
    service = ExtractionService(sessions, cast(DeepSeekClient, client))
    try:
        first = await service.run(date(2026, 8, 1), date(2026, 9, 15), 10)
        repeat = await service.run(date(2026, 8, 1), date(2026, 9, 15), 10)
        assert (first.failed, repeat.claimed, client.calls) == (1, 0, 1)
        connection = await postgres_database.connect()
        try:
            row = await connection.fetchrow(
                "SELECT status,error_code FROM llm_calls WHERE article_version_id=$1",
                version_id,
            )
            assert dict(row) == {
                "status": "extraction_unknown",
                "error_code": "unknown_transport_failure",
            }
        finally:
            await connection.close()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auth_failure_stops_batch_immediately(postgres_database: Any) -> None:
    await _seed_version(postgres_database, sources=1)
    await _seed_version(postgres_database, sources=1)
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = ErrorClient(
        DeepSeekError("unauthorized", code="authentication_failed", stop_batch=True)
    )
    try:
        result = await ExtractionService(sessions, cast(DeepSeekClient, client)).run(
            date(2026, 8, 1), date(2026, 9, 15), 10
        )
        assert (result.claimed, result.failed, result.stopped, client.calls) == (1, 1, True, 1)
        repeat = await ExtractionService(sessions, cast(DeepSeekClient, client)).run(
            date(2026, 8, 1), date(2026, 9, 15), 10
        )
        assert (repeat.claimed, repeat.stopped, client.calls) == (0, True, 1)
        connection = await postgres_database.connect()
        try:
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM article_candidates WHERE status='needs_review'"
                )
                >= 1
            )
        finally:
            await connection.close()
    finally:
        await engine.dispose()
