from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from radar.ingest.core import FeedEntry, FetchResult
from radar.ingest.worker_service import WorkerService
from radar.ingest_repository import IngestRepository
from radar.models import ArticleDiscoveryRow, IngestJobRow, IngestRunRow, SourceRow


class AsyncContext:
    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return None

    def __init__(self, value):
        self.value = value


class Result:
    def __init__(self, scalar=None, rows=None):
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.scalar

    def all(self):
        return self.rows


class Sessions:
    def __init__(self, *sessions):
        self.sessions = iter(sessions)

    def __call__(self):
        return AsyncContext(next(self.sessions))


class SourceSession:
    def __init__(self, source):
        self.source = source

    async def get(self, *_args):
        return self.source


class DiscoverySession:
    def __init__(self, job, source, run, remaining=25):
        self.job = job
        self.source = source
        self.run = run
        self.remaining = remaining
        self.added = []
        self.article_inserts = 0

    def begin(self):
        return AsyncContext(self)

    async def scalar(self, statement):
        sql = str(statement)
        if "FROM ingest_jobs" in sql:
            return self.job
        if "FROM sources" in sql:
            return self.source
        if "FROM article_discoveries" in sql:
            return None
        if "FROM ingest_runs" in sql:
            return self.run
        if "count(*)" in sql:
            return self.remaining
        raise AssertionError(sql)

    async def execute(self, statement):
        self.article_inserts += 1
        return Result()

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        return None


def make_rows():
    run_id = uuid4()
    source = SourceRow(
        id=uuid4(),
        name="source",
        feed_url="https://feed.example/rss",
        enabled=True,
        health="ok",
        consecutive_failures=0,
        canonical_host="feed.example",
        channel_type="rss",
    )
    job = IngestJobRow(
        id=uuid4(),
        run_id=run_id,
        source_id=source.id,
        job_key=f"source:{run_id}:{source.id}",
        stage="feed_discovery",
        payload={},
        state="running",
        attempts=1,
        max_attempts=3,
        not_before=datetime.now(UTC),
        lease_owner="worker",
        lease_until=datetime.now(UTC) + timedelta(minutes=1),
        lease_generation=1,
    )
    run = IngestRunRow(
        id=run_id,
        idempotency_key="run",
        payload_hash="hash",
        trigger_type="manual",
        status="running",
        discovered_urls=0,
        fetched_articles=0,
        new_articles=0,
        updated_articles=0,
        event_candidates=0,
        parser_failures=0,
        failed_jobs=0,
        cost_status="unknown",
    )
    return source, job, run


@pytest.mark.asyncio
async def test_discovery_persists_all_25_jobs_before_accepting_etag(monkeypatch) -> None:
    source, job, run = make_rows()
    transaction = DiscoverySession(job, source, run)
    entries = [
        FeedEntry(
            f"Item {index}",
            f"https://example.com/{index}",
            f"https://example.com/{index}?utm_source=feed",
            None,
        )
        for index in range(25)
    ]

    async def fetch(*_args, **_kwargs):
        return FetchResult(200, source.feed_url, b"feed", '"v2"', "today")

    monkeypatch.setattr("radar.ingest.worker_service.fetch_public", fetch)
    monkeypatch.setattr("radar.ingest.worker_service.parse_feed", lambda _body: entries)
    service = WorkerService(Sessions(SourceSession(source), transaction), SimpleNamespace())
    await service.process(job)

    discoveries = [row for row in transaction.added if isinstance(row, ArticleDiscoveryRow)]
    assert len(discoveries) == 25
    assert transaction.article_inserts == 25
    assert discoveries[-1].original_url.endswith("?utm_source=feed")
    assert source.etag == '"v2"'
    assert source.health == "healthy"
    assert run.discovered_urls == 25
    assert job.state == "succeeded"


@pytest.mark.asyncio
async def test_304_does_not_touch_existing_article_jobs(monkeypatch) -> None:
    source, job, run = make_rows()
    transaction = DiscoverySession(job, source, run, remaining=7)

    async def fetch(*_args, **_kwargs):
        return FetchResult(304, source.feed_url, b"", '"v1"', None)

    monkeypatch.setattr("radar.ingest.worker_service.fetch_public", fetch)
    monkeypatch.setattr(
        "radar.ingest.worker_service.parse_feed",
        lambda _body: pytest.fail("304 must not parse a feed"),
    )
    service = WorkerService(Sessions(SourceSession(source), transaction), SimpleNamespace())
    await service.process(job)

    assert transaction.article_inserts == 0
    assert transaction.remaining == 7
    assert run.discovered_urls == 0
    assert job.state == "succeeded"


def test_job_and_discovery_constraints_are_persistent() -> None:
    assert IngestJobRow.__table__.c.job_key.unique is True
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in ArticleDiscoveryRow.__table__.constraints
    }
    assert ("run_id", "source_id", "canonical_url") in constraint_columns


class FinishSession:
    def __init__(self, job, run, source):
        self.job = job
        self.run = run
        self.source = source
        self.parser_updates = 0

    def begin(self):
        return AsyncContext(self)

    async def scalar(self, statement):
        sql = str(statement)
        if "FROM ingest_jobs" in sql:
            return self.job
        if "FROM sources" in sql:
            return self.source
        return self.run

    async def execute(self, statement):
        sql = str(statement)
        if sql.startswith("UPDATE ingest_runs SET parser_failures"):
            self.parser_updates += 1
            return Result()
        assert "GROUP BY ingest_jobs.state" in sql
        return Result(rows=[("failed", 1)])

    async def scalars(self, statement):
        assert "ingest_jobs.last_error" in str(statement)
        return Result(rows=["boom"])

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_finish_final_attempt_marks_run_failed_with_summary() -> None:
    source, job, run = make_rows()
    job.attempts = job.max_attempts
    session = FinishSession(job, run, source)
    repository = IngestRepository(Sessions(session))

    accepted = await repository.finish(
        job.id, str(job.lease_owner), job.lease_generation, False, "boom"
    )

    assert accepted is True
    assert job.state == "failed"
    assert run.status == "failed"
    assert run.failed_jobs == 1
    assert run.finished_at is not None
    assert run.error_summary == "boom"
    assert source.health == "degraded"
    assert source.consecutive_failures == 1
    assert session.parser_updates == 0


@pytest.mark.asyncio
async def test_article_parser_failure_is_counted_separately_from_http_failure() -> None:
    source, job, run = make_rows()
    job.stage = "article_fetch"
    job.attempts = job.max_attempts
    parser_session = FinishSession(job, run, source)
    repository = IngestRepository(Sessions(parser_session))

    await repository.finish(
        job.id,
        str(job.lease_owner),
        job.lease_generation,
        False,
        "document parse failed",
        parser_failure=True,
    )

    assert parser_session.parser_updates == 1
    assert source.consecutive_failures == 0
    assert source.health == "ok"
