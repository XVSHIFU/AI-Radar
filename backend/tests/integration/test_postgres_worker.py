from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.ingest import worker_service as worker_module
from radar.ingest.core import FetchResult
from radar.ingest.worker_service import WorkerService
from radar.ingest_repository import IngestRepository
from radar.models import (
    ArticleCandidateRow,
    ArticleVersionRow,
    IngestRunRow,
    SourceRow,
)

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_worker_versions_changed_content_and_deduplicates_unchanged_content(
    postgres_database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = IngestRepository(sessions)
    source = SourceRow(
        id=uuid4(),
        name=f"worker-source-{uuid4()}",
        feed_url=f"https://example.com/{uuid4()}/feed",
        enabled=True,
        health="healthy",
        consecutive_failures=0,
        canonical_host="example.com",
        channel_type="rss",
    )
    article_url = f"https://example.com/articles/{uuid4()}"
    feed_body = (
        "<rss version='2.0'><channel><title>Integration</title><item>"
        f"<title>Versioned article</title><link>{article_url}</link>"
        "<pubDate>Thu, 10 Sep 2026 03:00:00 GMT</pubDate>"
        "</item></channel></rss>"
    ).encode()
    article_body = b"<main><p>First immutable body.</p></main>"

    async def fetch(_client: object, url: str, **_kwargs: object) -> FetchResult:
        body = feed_body if url == source.feed_url else article_body
        return FetchResult(200, url, body, None, None)

    monkeypatch.setattr(worker_module, "fetch_public", fetch)
    service = WorkerService(sessions, SimpleNamespace())

    async def ingest_once() -> IngestRunRow:
        run, _ = await repository.create_run([source.id], f"worker:{uuid4()}")
        discovery = await repository.claim("integration-worker")
        assert discovery is not None and discovery.stage == "feed_discovery"
        await service.process(discovery)
        article = await repository.claim("integration-worker")
        assert article is not None and article.stage == "article_fetch"
        await service.process(article)
        async with sessions() as session:
            stored = await session.get(IngestRunRow, run.id)
            assert stored is not None
            return stored

    try:
        async with sessions() as session, session.begin():
            session.add(source)

        first = await ingest_once()
        article_body = b"<main><p>Second immutable body.</p></main>"
        second = await ingest_once()
        third = await ingest_once()

        async with sessions() as session:
            versions = await session.scalar(
                select(func.count())
                .select_from(ArticleVersionRow)
                .where(ArticleVersionRow.source_url == article_url)
            )
            candidates = await session.scalar(
                select(func.count())
                .select_from(ArticleCandidateRow)
                .where(ArticleCandidateRow.source_id == source.id)
            )
            unbound = await session.scalar(
                select(func.count())
                .select_from(ArticleCandidateRow)
                .where(
                    ArticleCandidateRow.source_id == source.id,
                    ArticleCandidateRow.article_version_id.is_(None),
                )
            )
            published_dates = list(
                (
                    await session.scalars(
                        select(ArticleVersionRow.published_at).where(
                            ArticleVersionRow.source_url == article_url
                        )
                    )
                ).all()
            )

        assert (versions, candidates, unbound) == (2, 2, 0)
        assert all(
            item is not None and item.date().isoformat() == "2026-09-10" for item in published_dates
        )
        assert first.status == second.status == third.status == "success"
        assert (first.new_articles, first.updated_articles, first.event_candidates) == (1, 0, 1)
        assert (second.new_articles, second.updated_articles, second.event_candidates) == (0, 1, 1)
        assert (third.new_articles, third.updated_articles, third.event_candidates) == (0, 0, 0)
    finally:
        await engine.dispose()
