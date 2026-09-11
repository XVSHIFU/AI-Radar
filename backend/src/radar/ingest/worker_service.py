import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import (
    ArticleCandidateRow,
    ArticleDiscoveryRow,
    ArticleRow,
    ArticleVersionRow,
    IngestJobRow,
    IngestRunRow,
    SourceRow,
)
from .core import fetch_public, parse_document, parse_feed


class LeaseLost(RuntimeError):
    pass


def article_job_key(run_id: object, canonical_url: str) -> str:
    digest = hashlib.sha256(canonical_url.encode()).hexdigest()
    return f"article:{run_id}:{digest}"


class WorkerService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], client: httpx.AsyncClient):
        self.sessions = sessions
        self.client = client

    async def process(self, job: IngestJobRow) -> None:
        if job.stage == "feed_discovery":
            await self._discover(job)
        elif job.stage == "article_fetch":
            await self._fetch_article(job)
        else:
            raise ValueError(f"unsupported ingest stage: {job.stage}")

    async def _source(self, job: IngestJobRow) -> SourceRow:
        async with self.sessions() as session:
            source = await session.get(SourceRow, job.source_id)
        if source is None or not source.enabled:
            raise ValueError("source is not configured and enabled")
        return source

    @staticmethod
    async def _locked_job(session: AsyncSession, job: IngestJobRow) -> IngestJobRow:
        locked = await session.scalar(
            select(IngestJobRow).where(IngestJobRow.id == job.id).with_for_update()
        )
        now = datetime.now(UTC)
        if (
            locked is None
            or locked.lease_owner != job.lease_owner
            or locked.lease_generation != job.lease_generation
            or locked.state != "running"
            or locked.lease_until is None
            or locked.lease_until < now
        ):
            raise LeaseLost("worker lease is no longer current")
        return locked

    async def _discover(self, job: IngestJobRow) -> None:
        source = await self._source(job)
        feed = await fetch_public(
            self.client, source.feed_url, etag=source.etag, last_modified=source.last_modified
        )
        entries = [] if feed.status == 304 else parse_feed(feed.body)
        async with self.sessions() as session, session.begin():
            locked = await self._locked_job(session, job)
            source_row = await session.scalar(
                select(SourceRow).where(SourceRow.id == source.id).with_for_update()
            )
            assert source_row is not None
            new_discoveries = 0
            for entry in entries:
                discovery = await session.scalar(
                    select(ArticleDiscoveryRow).where(
                        ArticleDiscoveryRow.run_id == job.run_id,
                        ArticleDiscoveryRow.source_id == source.id,
                        ArticleDiscoveryRow.canonical_url == entry.url,
                    )
                )
                if discovery is None:
                    session.add(
                        ArticleDiscoveryRow(
                            id=uuid4(),
                            run_id=job.run_id,
                            source_id=source.id,
                            canonical_url=entry.url,
                            original_url=entry.original_url,
                            title=entry.title,
                            published=entry.published,
                        )
                    )
                    new_discoveries += 1
                key = article_job_key(job.run_id, entry.url)
                await session.execute(
                    insert(IngestJobRow)
                    .values(
                        id=uuid4(),
                        run_id=job.run_id,
                        source_id=source.id,
                        job_key=key,
                        stage="article_fetch",
                        payload={"canonical_url": entry.url},
                        state="queued",
                        attempts=0,
                        max_attempts=3,
                        lease_generation=0,
                    )
                    .on_conflict_do_nothing(index_elements=["job_key"])
                )
            await session.flush()
            run = await session.scalar(
                select(IngestRunRow).where(IngestRunRow.id == job.run_id).with_for_update()
            )
            assert run is not None
            run.discovered_urls += new_discoveries
            source_row.etag = feed.etag or source_row.etag
            source_row.last_modified = feed.last_modified or source_row.last_modified
            source_row.last_checked_at = datetime.now(UTC)
            source_row.last_success_at = datetime.now(UTC)
            source_row.consecutive_failures = 0
            locked.state = "succeeded"
            locked.lease_owner = None
            locked.lease_until = None
            await self._complete_run_if_done(session, run)

    async def _fetch_article(self, job: IngestJobRow) -> None:
        requested_url = str(job.payload["canonical_url"])
        response = await fetch_public(self.client, requested_url)
        canonical_url = response.final_url
        document = parse_document(response.body)
        async with self.sessions() as session, session.begin():
            locked = await self._locked_job(session, job)
            run = await session.scalar(
                select(IngestRunRow).where(IngestRunRow.id == job.run_id).with_for_update()
            )
            assert run is not None
            await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(canonical_url))))
            proposed_article_id = uuid4()
            inserted_article_id = (
                await session.execute(
                    insert(ArticleRow)
                    .values(
                        id=proposed_article_id, source_id=job.source_id, canonical_url=canonical_url
                    )
                    .on_conflict_do_nothing(index_elements=["canonical_url"])
                    .returning(ArticleRow.id)
                )
            ).scalar_one_or_none()
            is_new = inserted_article_id is not None
            article_id = inserted_article_id or await session.scalar(
                select(ArticleRow.id).where(ArticleRow.canonical_url == canonical_url)
            )
            assert article_id is not None
            if is_new:
                run.new_articles += 1
            discovery = await session.scalar(
                select(ArticleDiscoveryRow)
                .where(
                    ArticleDiscoveryRow.run_id == job.run_id,
                    ArticleDiscoveryRow.canonical_url == requested_url,
                )
                .order_by(ArticleDiscoveryRow.discovered_at)
            )
            inserted_version_id = (
                await session.execute(
                    insert(ArticleVersionRow)
                    .values(
                        id=uuid4(),
                        article_id=article_id,
                        title=discovery.title if discovery else "",
                        source_url=response.final_url,
                        published_at=None,
                        paragraphs=document.paragraphs,
                        content_hash=document.content_hash,
                    )
                    .on_conflict_do_nothing(index_elements=["article_id", "content_hash"])
                    .returning(ArticleVersionRow.id)
                )
            ).scalar_one_or_none()
            if inserted_version_id is not None and not is_new:
                run.updated_articles += 1
            discoveries = list(
                (
                    await session.scalars(
                        select(ArticleDiscoveryRow).where(
                            ArticleDiscoveryRow.run_id == job.run_id,
                            ArticleDiscoveryRow.canonical_url == requested_url,
                        )
                    )
                ).all()
            )
            candidates_added = 0
            for item in discoveries:
                item.article_id = article_id
                inserted_candidate_id = (
                    await session.execute(
                        insert(ArticleCandidateRow)
                        .values(
                            id=uuid4(),
                            run_id=job.run_id,
                            source_id=item.source_id,
                            canonical_url=canonical_url,
                            original_url=item.original_url,
                            title=item.title,
                            status="needs_review",
                        )
                        .on_conflict_do_nothing(index_elements=["source_id", "canonical_url"])
                        .returning(ArticleCandidateRow.id)
                    )
                ).scalar_one_or_none()
                candidates_added += int(inserted_candidate_id is not None)
            run.fetched_articles += 1
            run.event_candidates += candidates_added
            locked.state = "succeeded"
            locked.lease_owner = None
            locked.lease_until = None
            await session.flush()
            await self._complete_run_if_done(session, run)

    @staticmethod
    async def _complete_run_if_done(session: AsyncSession, run: IngestRunRow) -> None:
        remaining = await session.scalar(
            select(func.count())
            .select_from(IngestJobRow)
            .where(
                IngestJobRow.run_id == run.id,
                IngestJobRow.state.in_(("queued", "retry_wait", "running")),
            )
        )
        if not remaining:
            failed = (
                await session.scalar(
                    select(func.count())
                    .select_from(IngestJobRow)
                    .where(IngestJobRow.run_id == run.id, IngestJobRow.state == "failed")
                )
                or 0
            )
            succeeded = (
                await session.scalar(
                    select(func.count())
                    .select_from(IngestJobRow)
                    .where(IngestJobRow.run_id == run.id, IngestJobRow.state == "succeeded")
                )
                or 0
            )
            run.failed_jobs = failed
            run.status = "partial" if failed and succeeded else ("failed" if failed else "success")
            run.finished_at = datetime.now(UTC)
