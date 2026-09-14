"""Restartable historical discovery; feeds alone are not a complete web archive."""

import argparse
import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import feedparser  # type: ignore[import-untyped]
import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import REPO_ROOT, get_settings
from .ingest.archives import (
    arxiv_query,
    entry_day,
    in_range,
    parse_anthropic_archive,
    parse_aws_archive,
    parse_deepseek_archive,
)
from .ingest.core import FeedEntry, fetch_public, parse_feed
from .ingest.dns import configured_resolver
from .ingest.public_transport import PublicAsyncTransport, Resolver
from .ingest.throttle import retry_after_seconds
from .ingest.worker_service import article_job_key
from .models import (
    ArticleCandidateRow,
    ArticleDiscoveryRow,
    ArticleRow,
    ArticleVersionRow,
    IngestJobRow,
    IngestRunRow,
    SourceRow,
)
from .register_sources import CURATED_SOURCE_CANDIDATES


@dataclass(frozen=True)
class Archive:
    name: str
    url: str
    kind: str = "rss"


ARCHIVES = [
    Archive(
        s.name,
        s.feed_url,
        "arxiv" if s.name.startswith("arXiv") else ("aws" if s.name.startswith("AWS") else "rss"),
    )
    for s in CURATED_SOURCE_CANDIDATES
] + [
    Archive("OpenAI", "https://openai.com/news/rss.xml"),
    Archive("Anthropic", "https://www.anthropic.com/news", "anthropic"),
    Archive("DeepSeek", "https://api-docs.deepseek.com/updates/", "deepseek"),
]


async def register(sessions: async_sessionmaker[AsyncSession], source: Archive) -> SourceRow:
    async with sessions() as session, session.begin():
        await session.execute(
            insert(SourceRow)
            .values(
                id=uuid5(NAMESPACE_URL, source.url),
                name=source.name,
                feed_url=source.url,
                enabled=True,
                health="unverified",
                canonical_host=httpx.URL(source.url).host,
                channel_type="archive" if source.kind in ("anthropic", "deepseek") else "rss",
            )
            .on_conflict_do_nothing(index_elements=["name"])
        )
        row = await session.scalar(select(SourceRow).where(SourceRow.name == source.name))
        assert row is not None
        return row


class Collector:
    def __init__(self, client: httpx.AsyncClient, resolver: Resolver, refresh: bool) -> None:
        self.client, self.resolver, self.refresh = client, resolver, refresh
        self.cache = REPO_ROOT / ".run" / "archive-cache"
        self.cache.mkdir(parents=True, exist_ok=True)

    async def read(self, url: str) -> bytes:
        target = self.cache / hashlib.sha256(url.encode()).hexdigest()
        if not self.refresh and target.exists():
            age = datetime.now(UTC).timestamp() - target.stat().st_mtime
            if age < 86400:
                return target.read_bytes()
        result = await fetch_public(self.client, url, resolver=self.resolver)
        temporary = target.with_suffix("." + uuid4().hex + ".tmp")
        temporary.write_bytes(result.body)
        temporary.replace(target)
        await asyncio.sleep(3.1)
        return result.body

    async def discover(
        self,
        source: Archive,
        start: date,
        end: date,
        max_pages: int,
    ) -> tuple[list[FeedEntry], dict[str, Any]]:
        entries: dict[str, FeedEntry] = {}
        report: dict[str, Any] = {
            "source": source.name,
            "archive": source.url,
            "kind": source.kind,
            "pages": 0,
            "status": "partial",
            "unknown_dates": 0,
        }
        seen: set[str] = set()
        try:
            for page in range(max_pages):
                if source.kind == "arxiv":
                    url = arxiv_query(start, end, page * 200)
                elif source.kind == "aws":
                    url = (
                        "https://aws.amazon.com/blogs/machine-learning/"
                        if page == 0
                        else f"https://aws.amazon.com/blogs/machine-learning/page/{page + 1}/"
                    )
                else:
                    url = source.url
                body = await self.read(url)
                digest = hashlib.sha256(body).hexdigest()
                if digest in seen:
                    report["status"] = "repeated_page"
                    break
                seen.add(digest)
                if source.kind == "aws":
                    rows = parse_aws_archive(body)
                elif source.kind == "anthropic":
                    rows = parse_anthropic_archive(body)
                elif source.kind == "deepseek":
                    rows = parse_deepseek_archive(body)
                else:
                    rows = parse_feed(body)
                report["pages"] += 1
                if not rows:
                    report["status"] = "empty_or_unrecognized_archive"
                    break
                for row in rows:
                    if entry_day(row) is None:
                        report["unknown_dates"] += 1
                    if in_range(row, start, end):
                        entries[row.url] = row
                days = [day for row in rows if (day := entry_day(row)) is not None]
                if days:
                    report["oldest_seen"] = min(
                        report.get("oldest_seen", "9999"),
                        min(days).isoformat(),
                    )
                    report["newest_seen"] = max(
                        report.get("newest_seen", ""),
                        max(days).isoformat(),
                    )
                if source.kind == "arxiv":
                    feed = feedparser.parse(body)
                    total = int(feed.feed.get("opensearch_totalresults", 0))
                    report["archive_total"] = total
                    if (page + 1) * 200 >= total:
                        report["status"] = "archive_query_exhausted"
                        break
                elif source.kind == "aws":
                    if days and max(days) < start:
                        report["status"] = "reached_before_start"
                        break
                else:
                    report["status"] = "archive_scanned"
                    report["covers_start"] = bool(days and min(days) <= start)
                    break
            else:
                report["status"] = "page_limit_reached"
        except (httpx.HTTPError, OSError, ValueError) as exc:
            report["status"] = "deferred" if retry_after_seconds(exc) else "failed"
            report["error"] = f"{type(exc).__name__}: {str(exc) or 'request failed'}"[:400]
            report["retry_after_seconds"] = retry_after_seconds(exc)
        report["selected"] = len(entries)
        return list(entries.values()), report


async def enqueue(
    sessions: async_sessionmaker[AsyncSession],
    selections: list[tuple[SourceRow, list[FeedEntry]]],
    start: date,
    end: date,
    replace_pending: bool = False,
) -> dict[str, Any]:
    key = f"backfill:{start}:{end}"
    async with sessions() as session, session.begin():
        await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
        run = await session.scalar(select(IngestRunRow).where(IngestRunRow.idempotency_key == key))
        if run is None:
            run = IngestRunRow(
                id=uuid4(),
                idempotency_key=key,
                payload_hash=hashlib.sha256(key.encode()).hexdigest(),
                trigger_type="backfill",
                status="queued",
                discovered_urls=0,
                fetched_articles=0,
                new_articles=0,
                updated_articles=0,
                event_candidates=0,
                parser_failures=0,
                failed_jobs=0,
            )
            session.add(run)
            await session.flush()
        # The caller pauses worker/scheduler before explicitly superseding old work.
        if replace_pending:
            await session.execute(
                update(IngestJobRow)
                .where(
                    IngestJobRow.run_id != run.id,
                    IngestJobRow.state.in_(("queued", "retry_wait", "running")),
                )
                .values(
                    state="cancelled",
                    lease_owner=None,
                    lease_until=None,
                    last_error="superseded by explicit historical date-range backfill",
                )
            )
            await session.execute(
                update(IngestRunRow)
                .where(
                    IngestRunRow.id != run.id,
                    IngestRunRow.status.in_(("queued", "running")),
                )
                .values(status="cancelled", finished_at=datetime.now(UTC))
            )
        new_jobs = reused = discovered = added_candidates = 0
        for source, entries in selections:
            for entry in entries:
                discovery_id = (
                    await session.execute(
                        insert(ArticleDiscoveryRow)
                        .values(
                            id=uuid4(),
                            run_id=run.id,
                            source_id=source.id,
                            canonical_url=entry.url,
                            original_url=entry.original_url,
                            title=entry.title,
                            published=entry.published,
                        )
                        .on_conflict_do_nothing(
                            index_elements=["run_id", "source_id", "canonical_url"],
                        )
                        .returning(ArticleDiscoveryRow.id)
                    )
                ).scalar_one_or_none()
                discovered += int(discovery_id is not None)
                version = await session.scalar(
                    select(ArticleVersionRow)
                    .join(ArticleRow)
                    .where(
                        ArticleRow.canonical_url == entry.url,
                    )
                    .order_by(ArticleVersionRow.fetched_at.desc())
                    .limit(1)
                )
                if version is not None:
                    reused += 1
                    await session.execute(
                        update(ArticleDiscoveryRow)
                        .where(
                            ArticleDiscoveryRow.run_id == run.id,
                            ArticleDiscoveryRow.source_id == source.id,
                            ArticleDiscoveryRow.canonical_url == entry.url,
                        )
                        .values(article_id=version.article_id)
                    )
                    candidate_id = (
                        await session.execute(
                            insert(ArticleCandidateRow)
                            .values(
                                id=uuid4(),
                                run_id=run.id,
                                source_id=source.id,
                                canonical_url=entry.url,
                                original_url=entry.original_url,
                                title=entry.title,
                                article_version_id=version.id,
                                status="needs_review",
                            )
                            .on_conflict_do_nothing(
                                index_elements=["source_id", "article_version_id"],
                            )
                            .returning(ArticleCandidateRow.id)
                        )
                    ).scalar_one_or_none()
                    added_candidates += int(candidate_id is not None)
                    continue
                job_id = (
                    await session.execute(
                        insert(IngestJobRow)
                        .values(
                            id=uuid4(),
                            run_id=run.id,
                            source_id=source.id,
                            job_key=article_job_key(run.id, entry.url),
                            stage="article_fetch",
                            payload={"canonical_url": entry.url},
                        )
                        .on_conflict_do_nothing(
                            index_elements=["job_key"],
                        )
                        .returning(IngestJobRow.id)
                    )
                ).scalar_one_or_none()
                new_jobs += int(job_id is not None)
        run.discovered_urls += discovered
        run.event_candidates += added_candidates
        pending = await session.scalar(
            select(func.count())
            .select_from(IngestJobRow)
            .where(
                IngestJobRow.run_id == run.id,
                IngestJobRow.state.in_(("queued", "retry_wait", "running")),
            )
        )
        run.status = "queued" if pending else "success"
        run.finished_at = None if pending else datetime.now(UTC)
        return {
            "run_id": str(run.id),
            "new_discoveries": discovered,
            "new_jobs": new_jobs,
            "reused_versions": reused,
            "new_candidates": added_candidates,
            "status": run.status,
            "total_discoveries": run.discovered_urls,
        }


async def run(args: argparse.Namespace) -> None:
    start, end = date.fromisoformat(args.date_from), date.fromisoformat(args.date_to)
    if start > end:
        raise ValueError("date_from must not exceed date_to")
    settings = get_settings()
    url = settings.sqlalchemy_url()
    if settings.radar_data_mode != "postgres" or url is None:
        raise RuntimeError("historical backfill requires PostgreSQL")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    resolver = configured_resolver(settings.fetch_dns_mode)
    reports: list[dict[str, Any]] = []
    selections = []
    try:
        async with httpx.AsyncClient(
            transport=PublicAsyncTransport(resolver=resolver),
            trust_env=False,
            headers={"User-Agent": "AI-Radar/0.1 (public research archive; sequential requests)"},
        ) as client:
            collector = Collector(client, resolver, args.refresh)
            for definition in ARCHIVES:
                if args.source and definition.name not in args.source:
                    continue
                source = await register(sessions, definition)
                if not source.enabled:
                    reports.append({"source": source.name, "status": "disabled", "selected": 0})
                    continue
                async with sessions() as session:
                    known = list(
                        (
                            await session.scalars(
                                select(ArticleDiscoveryRow)
                                .where(
                                    ArticleDiscoveryRow.source_id == source.id,
                                )
                                .order_by(ArticleDiscoveryRow.discovered_at)
                            )
                        ).all()
                    )
                prior = {
                    row.canonical_url: FeedEntry(
                        row.title,
                        row.canonical_url,
                        row.original_url,
                        row.published,
                    )
                    for row in known
                }
                prior = {url: row for url, row in prior.items() if in_range(row, start, end)}
                entries: list[FeedEntry]
                report: dict[str, Any]
                if source.cooldown_until and source.cooldown_until > datetime.now(UTC):
                    entries = []
                    report = {"source": source.name, "status": "cooling_down", "selected": 0}
                else:
                    entries, report = await collector.discover(
                        definition,
                        start,
                        end,
                        args.max_pages,
                    )
                combined = dict(prior)
                combined.update({entry.url: entry for entry in entries})
                report["prior_discoveries_in_range"] = len(prior)
                report["selected_total"] = len(combined)
                reports.append(report)
                selections.append((source, list(combined.values())))
                if delay := report.get("retry_after_seconds"):
                    async with sessions() as session, session.begin():
                        await session.execute(
                            update(SourceRow)
                            .where(SourceRow.id == source.id)
                            .values(
                                cooldown_until=datetime.now(UTC) + timedelta(seconds=delay),
                                health="rate_limited",
                            )
                        )
                print(json.dumps(report, ensure_ascii=False), flush=True)
        result = await enqueue(sessions, selections, start, end, args.replace_pending)
        report = {
            "captured_at": datetime.now(UTC).isoformat(),
            "date_from": str(start),
            "date_to": str(end),
            "timezone": "Asia/Shanghai",
            "sources": reports,
            "queue": result,
            "model_calls": 0,
            "scope": "configured public archives; completeness limited by archive availability",
        }
        target = REPO_ROOT / ".run" / f"backfill-{start}-{end}.json"
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            previous = json.loads(target.read_text())
            combined_reports = {row["source"]: row for row in previous.get("sources", [])}
            combined_reports.update({row["source"]: row for row in reports})
            report["sources"] = list(combined_reports.values())
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--source", action="append")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--replace-pending", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 500:
        parser.error("--max-pages must be between 1 and 500")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
