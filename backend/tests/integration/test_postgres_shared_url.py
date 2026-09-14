from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.ingest import worker_service as worker_module
from radar.ingest.core import FetchResult
from radar.ingest.worker_service import WorkerService
from radar.ingest_repository import IngestRepository
from radar.models import (
    ArticleCandidateRow,
    ArticleDiscoveryRow,
    ArticleRow,
    ArticleVersionRow,
    SourceRow,
)

pytestmark = pytest.mark.postgres


def _source(label: str) -> SourceRow:
    return SourceRow(
        id=uuid4(),
        name=f"shared-{label}-{uuid4()}",
        feed_url=f"https://{label}.example.com/{uuid4()}/feed",
        enabled=True,
        health="healthy",
        consecutive_failures=0,
        canonical_host=f"{label}.example.com",
        channel_type="rss",
    )


@pytest.mark.asyncio
async def test_shared_url_is_fetched_once_and_fans_out_version_bound_candidates(
    postgres_database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = IngestRepository(sessions)
    sources = [_source("alpha"), _source("beta")]
    article_url = f"https://publisher.example.com/{uuid4()}"
    metadata = {
        sources[0].id: ("Alpha title", "Thu, 10 Sep 2026 03:00:00 GMT"),
        sources[1].id: ("Beta title", "Fri, 11 Sep 2026 04:00:00 GMT"),
    }

    def feed(title: str, published: str) -> bytes:
        return (
            "<rss version='2.0'><channel><title>Shared URL</title><item>"
            f"<title>{title}</title><link>{article_url}</link>"
            f"<pubDate>{published}</pubDate></item></channel></rss>"
        ).encode()

    async def fetch(_client: object, url: str, **_kwargs: object) -> FetchResult:
        for source in sources:
            if url == source.feed_url:
                return FetchResult(200, url, feed(*metadata[source.id]), None, None)
        return FetchResult(
            200,
            article_url,
            b"<main><p>One body shared by two discovery sources.</p></main>",
            None,
            None,
        )

    monkeypatch.setattr(worker_module, "fetch_public", fetch)
    service = WorkerService(sessions, SimpleNamespace())
    try:
        async with sessions() as session, session.begin():
            session.add_all(sources)
        run, _ = await repository.create_run(
            [source.id for source in sources], f"shared-url:{uuid4()}"
        )

        first_discovery = await repository.claim("shared-worker")
        assert first_discovery is not None
        await service.process(first_discovery)
        second_discovery = await repository.claim("shared-worker")
        assert second_discovery is not None
        assert second_discovery.stage == "feed_discovery"
        await service.process(second_discovery)
        article_job = await repository.claim("shared-worker")
        assert article_job is not None and article_job.stage == "article_fetch"
        await service.process(article_job)
        assert await repository.claim("shared-worker") is None

        async with sessions() as session:
            articles = list(
                (
                    await session.scalars(
                        select(ArticleRow).where(ArticleRow.canonical_url == article_url)
                    )
                ).all()
            )
            versions = list(
                (
                    await session.scalars(
                        select(ArticleVersionRow).where(
                            ArticleVersionRow.article_id == articles[0].id
                        )
                    )
                ).all()
            )
            discoveries = list(
                (
                    await session.scalars(
                        select(ArticleDiscoveryRow).where(ArticleDiscoveryRow.run_id == run.id)
                    )
                ).all()
            )
            candidates = list(
                (
                    await session.scalars(
                        select(ArticleCandidateRow).where(ArticleCandidateRow.run_id == run.id)
                    )
                ).all()
            )

        assert len(articles) == len(versions) == 1
        assert len(discoveries) == len(candidates) == 2
        assert {item.source_id for item in candidates} == {source.id for source in sources}
        assert {item.title for item in candidates} == {"Alpha title", "Beta title"}
        assert all(item.article_id == articles[0].id for item in discoveries)
        assert all(item.article_version_id == versions[0].id for item in candidates)
        owner_title, owner_published = metadata[article_job.source_id]
        assert versions[0].title == owner_title
        assert versions[0].published_at is not None
        assert versions[0].published_at.day == (10 if "10 Sep" in owner_published else 11)
    finally:
        await engine.dispose()
