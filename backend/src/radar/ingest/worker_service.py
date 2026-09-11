from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import (
    ArticleCandidateRow,
    ArticleRow,
    ArticleVersionRow,
    IngestJobRow,
    IngestRunRow,
    SourceRow,
)
from .core import FeedEntry, ParsedDocument, fetch_public, parse_document, parse_feed


class LeaseLost(RuntimeError):
    pass


class WorkerService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], client: httpx.AsyncClient):
        self.sessions = sessions
        self.client = client

    async def process(self, job: IngestJobRow) -> None:
        async with self.sessions() as session:
            source = await session.get(SourceRow, job.source_id)
        if source is None or not source.enabled:
            raise ValueError("source is not configured and enabled")
        feed = await fetch_public(
            self.client,
            source.feed_url,
            etag=source.etag,
            last_modified=source.last_modified,
        )
        if feed.status == 304:
            await self._record_unchanged(job, source, feed.etag, feed.last_modified)
            return
        entries = parse_feed(feed.body)
        documents: list[tuple[FeedEntry, ParsedDocument]] = []
        parser_failures = 0
        for entry in entries[:20]:
            try:
                response = await fetch_public(self.client, entry.url)
                documents.append((entry, parse_document(response.body)))
            except (httpx.HTTPError, ValueError):
                parser_failures += 1
        async with self.sessions() as session, session.begin():
            locked = await session.scalar(
                select(IngestJobRow).where(IngestJobRow.id == job.id).with_for_update()
            )
            if (
                locked is None
                or locked.lease_owner != job.lease_owner
                or locked.lease_generation != job.lease_generation
                or locked.state != "running"
            ):
                raise LeaseLost("worker lease is no longer current")
            source_row = await session.get(SourceRow, source.id)
            assert source_row is not None
            source_row.etag = feed.etag
            source_row.last_modified = feed.last_modified
            source_row.last_checked_at = datetime.now(UTC)
            source_row.last_success_at = datetime.now(UTC)
            source_row.consecutive_failures = 0
            run = await session.get(IngestRunRow, job.run_id)
            assert run is not None
            run.discovered_urls += len(entries)
            run.fetched_articles += len(documents)
            run.parser_failures += parser_failures
            for entry, document in documents:
                article = await session.scalar(
                    select(ArticleRow).where(
                        ArticleRow.source_id == source.id,
                        ArticleRow.canonical_url == entry.url,
                    )
                )
                if article is None:
                    article = ArticleRow(
                        id=uuid4(),
                        source_id=source.id,
                        canonical_url=entry.url,
                    )
                    session.add(article)
                    await session.flush()
                    run.new_articles += 1
                existing = await session.scalar(
                    select(ArticleVersionRow).where(
                        ArticleVersionRow.article_id == article.id,
                        ArticleVersionRow.content_hash == document.content_hash,
                    )
                )
                if existing is None:
                    session.add(
                        ArticleVersionRow(
                            id=uuid4(),
                            article_id=article.id,
                            title=entry.title,
                            source_url=entry.url,
                            published_at=None,
                            paragraphs=document.paragraphs,
                            content_hash=document.content_hash,
                        )
                    )
                    if run.new_articles == 0:
                        run.updated_articles += 1
                candidate = await session.scalar(
                    select(ArticleCandidateRow).where(
                        ArticleCandidateRow.source_id == source.id,
                        ArticleCandidateRow.canonical_url == entry.url,
                    )
                )
                if candidate is None:
                    session.add(
                        ArticleCandidateRow(
                            id=uuid4(),
                            run_id=run.id,
                            source_id=source.id,
                            canonical_url=entry.url,
                            original_url=entry.url,
                            title=entry.title,
                            status="needs_review",
                        )
                    )
                    run.event_candidates += 1

    async def _record_unchanged(
        self,
        job: IngestJobRow,
        source: SourceRow,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        async with self.sessions() as session, session.begin():
            locked = await session.scalar(
                select(IngestJobRow).where(IngestJobRow.id == job.id).with_for_update()
            )
            if (
                locked is None
                or locked.lease_owner != job.lease_owner
                or locked.lease_generation != job.lease_generation
            ):
                raise LeaseLost("worker lease is no longer current")
            row = await session.get(SourceRow, source.id)
            assert row is not None
            row.etag = etag or row.etag
            row.last_modified = last_modified or row.last_modified
            row.last_checked_at = datetime.now(UTC)
            row.last_success_at = datetime.now(UTC)
