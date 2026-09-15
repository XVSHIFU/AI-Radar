import json
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.deepseek_client import Completion, DeepSeekClient, DeepSeekError, ProviderUsage
from radar.extraction_schemas import ExtractionResult
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


def _event_json(
    quote: str, *, title: str = "新模型发布", event_date: str | None = None
) -> str:
    payload = {
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
        }
    if event_date is not None:
        payload.update(
            event_date=event_date,
            date_precision="day",
            date_basis="explicit_body",
            date_evidence_paragraph_id="p-0001",
        )
    return json.dumps(payload, ensure_ascii=False)


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
    article_id, first_version = await _seed_version(
        postgres_database,
        paragraph="Example AI released a model on 2026-09-01 with verified benchmarks.",
    )
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = StubClient(
        [_event_json("released a model on 2026-09-01", event_date="2026-09-01")]
    )
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
            assert event["date_basis"] == "explicit_body"
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
            assert evidence["quote_hash"] is not None
        finally:
            await connection.close()

        _, second_version = await _seed_version(
            postgres_database,
            article_id=article_id,
            sources=1,
            published_at=None,
            published_text="2026-09-15",
            paragraph="Example AI released version two on 2026-09-15 with longer context.",
        )
        client.contents.append(
            _event_json(
                "released version two on 2026-09-15",
                title="模型更新",
                event_date="2026-09-15",
            )
        )
        second = await service.run(date(2026, 9, 15), date(2026, 9, 15), 10)
        assert (second.claimed, second.published, client.calls) == (1, 1, 2)

        connection = await postgres_database.connect()
        try:
            event = await connection.fetchrow("SELECT * FROM events WHERE id=$1", event_id)
            assert event is not None
            assert event["content_version"] == 2
            assert event["event_date"] == date(2026, 9, 1)
            assert event["date_conflict"] is True
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
            invalid_call = await connection.fetchrow(
                "SELECT prompt_tokens,completion_tokens,total_tokens "
                "FROM llm_calls WHERE error_code='invalid_extraction' "
                "AND article_version_id IN ($1,$2)",
                irrelevant_version,
                invalid_version,
            )
            assert dict(invalid_call) == {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
            # Source UUID ordering is intentionally independent of insertion order.
            assert {statuses[irrelevant_version], statuses[invalid_version]} == {
                "filtered",
                "extraction_failed",
            }
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
                "SELECT status,error_code,prompt_tokens,completion_tokens,total_tokens "
                "FROM llm_calls WHERE article_version_id=$1",
                version_id,
            )
            assert dict(row) == {
                "status": "extraction_unknown",
                "error_code": "unknown_transport_failure",
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }
        finally:
            await connection.close()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_truncated_response_usage_is_persisted_without_event(postgres_database: Any) -> None:
    _, version_id = await _seed_version(
        postgres_database,
        sources=1,
        published_at=datetime(2026, 8, 7, 2, tzinfo=UTC),
    )
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = ErrorClient(
        DeepSeekError(
            "truncated",
            code="truncated_response",
            stop_batch=False,
            completion=Completion("{", "truncated-id", ProviderUsage(21, 9, 30)),
        )
    )
    try:
        result = await ExtractionService(sessions, cast(DeepSeekClient, client)).run(
            date(2026, 8, 7), date(2026, 8, 7), 1
        )
        assert (result.failed, client.calls) == (1, 1)
        connection = await postgres_database.connect()
        try:
            row = await connection.fetchrow(
                "SELECT status,error_code,provider_response_id,prompt_tokens,"
                "completion_tokens,total_tokens FROM llm_calls WHERE article_version_id=$1",
                version_id,
            )
            assert dict(row) == {
                "status": "extraction_failed",
                "error_code": "truncated_response",
                "provider_response_id": "truncated-id",
                "prompt_tokens": 21,
                "completion_tokens": 9,
                "total_tokens": 30,
            }
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM evidence WHERE article_version_id=$1", version_id
                )
                == 0
            )
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


@pytest.mark.asyncio
async def test_only_latest_uncalled_article_version_is_eligible(postgres_database: Any) -> None:
    connection = await postgres_database.connect()
    try:
        await connection.execute(
            "UPDATE llm_calls SET error_code=NULL "
            "WHERE error_code IN ('authentication_failed','insufficient_balance')"
        )
    finally:
        await connection.close()
    article_id, old_version = await _seed_version(
        postgres_database,
        sources=1,
        published_at=datetime(2026, 8, 5, 2, tzinfo=UTC),
        paragraph="Example AI released old model.",
    )
    _, new_version = await _seed_version(
        postgres_database,
        article_id=article_id,
        sources=1,
        published_at=datetime(2026, 8, 5, 3, tzinfo=UTC),
        paragraph="Example AI released new model.",
    )
    connection = await postgres_database.connect()
    try:
        await connection.execute(
            "UPDATE article_versions SET fetched_at=$1 WHERE id=$2",
            datetime(2026, 8, 5, 4, tzinfo=UTC),
            old_version,
        )
        await connection.execute(
            "UPDATE article_versions SET fetched_at=$1 WHERE id=$2",
            datetime(2026, 8, 5, 5, tzinfo=UTC),
            new_version,
        )
    finally:
        await connection.close()
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = StubClient([_event_json("released new model")])
    service = ExtractionService(sessions, cast(DeepSeekClient, client))
    try:
        result = await service.run(date(2026, 8, 5), date(2026, 8, 5), 1)
        remaining = await service._eligible_versions(date(2026, 8, 5), date(2026, 8, 5), 1)
        assert (result.claimed, result.published, client.calls) == (1, 1, 1)
        assert remaining == []
        connection = await postgres_database.connect()
        try:
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM llm_calls WHERE article_version_id=$1",
                    new_version,
                )
                == 1
            )
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM llm_calls WHERE article_version_id=$1",
                    old_version,
                )
                == 0
            )
        finally:
            await connection.close()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_claimed_old_version_cannot_overwrite_newer_publication(
    postgres_database: Any,
) -> None:
    connection = await postgres_database.connect()
    try:
        await connection.execute(
            "UPDATE llm_calls SET error_code=NULL "
            "WHERE error_code IN ('authentication_failed','insufficient_balance')"
        )
    finally:
        await connection.close()
    article_id, old_version = await _seed_version(
        postgres_database,
        sources=1,
        published_at=datetime(2026, 8, 6, 2, tzinfo=UTC),
        paragraph="Example AI released old model.",
    )
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = ExtractionService(sessions, cast(DeepSeekClient, StubClient([])))
    old_call = await service._claim(old_version)
    assert old_call is not None
    old_row = await service._version(old_version)
    _, new_version = await _seed_version(
        postgres_database,
        article_id=article_id,
        sources=1,
        published_at=datetime(2026, 8, 6, 3, tzinfo=UTC),
        paragraph="Example AI released new model.",
    )
    connection = await postgres_database.connect()
    try:
        await connection.execute(
            "UPDATE article_versions SET fetched_at=$1 WHERE id=$2",
            datetime(2026, 8, 6, 4, tzinfo=UTC),
            old_version,
        )
        await connection.execute(
            "UPDATE article_versions SET fetched_at=$1 WHERE id=$2",
            datetime(2026, 8, 6, 5, tzinfo=UTC),
            new_version,
        )
    finally:
        await connection.close()
    new_client = StubClient([_event_json("released new model", title="较新模型")])
    new_service = ExtractionService(sessions, cast(DeepSeekClient, new_client))
    try:
        published = await new_service.run(date(2026, 8, 6), date(2026, 8, 6), 1)
        assert (published.claimed, published.published) == (1, 1)
        old_extraction = ExtractionResult.model_validate_json(
            _event_json("released old model", title="过时模型")
        )
        await service._publish(
            old_call,
            old_row,
            date(2026, 8, 6),
            old_extraction,
            Completion("old", "old-response", ProviderUsage(10, 5, 15)),
        )
        connection = await postgres_database.connect()
        try:
            event = await connection.fetchrow(
                "SELECT events.* FROM events JOIN event_articles "
                "ON event_articles.event_id=events.id WHERE event_articles.article_id=$1",
                article_id,
            )
            assert event["title_zh"] == "较新模型"
            assert event["content_version"] == 1
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM evidence WHERE event_id=$1", event["id"]
                )
                == 1
            )
            assert (
                await connection.fetchval("SELECT status FROM llm_calls WHERE id=$1", old_call)
                == "superseded"
            )
            assert (
                await connection.fetchval(
                    "SELECT status FROM article_candidates WHERE article_version_id=$1",
                    old_version,
                )
                == "superseded"
            )
        finally:
            await connection.close()
    finally:
        await engine.dispose()
