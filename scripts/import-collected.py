"""SSH-only receiver, executed inside the existing worker container (no HTTP endpoint)."""

import asyncio
import base64
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from radar.article_rules import accept_feed_entry, classify_article
from radar.config import get_settings
from radar.container_entry import environment
from radar.ingest.core import canonicalize_url, parse_document, parse_feed
from radar.ingest.dates import published_datetime
from radar.models import (
    ArticleDiscoveryRow,
    ArticleRow,
    ArticleVersionRow,
    IngestRunRow,
    SourceRow,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def receive(batch):
    if batch.get("format") != 1 or len(batch["feeds"]) > 20:
        raise ValueError("unsupported collection batch")
    batch_id = UUID(batch["id"])
    digest = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
    os.environ.update(environment("worker", os.environ))
    get_settings.cache_clear()
    engine = create_async_engine(get_settings().sqlalchemy_url())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session, session.begin():
            # Serializes sync receivers, while ordinary cloud collection keeps running.
            await session.execute(select(func.pg_advisory_xact_lock(734196208)))
            existing = await session.get(IngestRunRow, batch_id)
            if existing:
                if existing.payload_hash != digest:
                    raise ValueError("batch ID reused with different contents")
                return {
                    "id": str(batch_id),
                    "replayed": True,
                    "new": existing.new_articles,
                }
            now = datetime.now(UTC)
            errors = list(batch.get("errors", []))
            run = IngestRunRow(
                id=batch_id,
                idempotency_key=f"ssh-sync:{batch_id}",
                payload_hash=digest,
                trigger_type="ssh_sync",
                status="success",
                new_articles=0,
                updated_articles=0,
                discovered_urls=0,
                fetched_articles=0,
                cost=0,
                cost_status="actual",
            )
            session.add(run)
            await session.flush()
            for feed in batch["feeds"]:
                url = canonicalize_url(feed["url"])
                name = feed["name"]
                source = await session.scalar(select(SourceRow).where(SourceRow.feed_url == url))
                if source is None:
                    # A relay-only source must not start cloud-side network jobs.
                    source = SourceRow(
                        id=uuid5(NAMESPACE_URL, url),
                        name=name,
                        feed_url=url,
                        enabled=False,
                        canonical_host=urlsplit(url).hostname,
                        channel_type="rss",
                    )
                    session.add(source)
                    await session.flush()
                if source.name != name:
                    raise ValueError("source name does not match configured feed")
                entries = [
                    e
                    for e in parse_feed(base64.b64decode(feed["rss"], validate=True))
                    if accept_feed_entry(name, e.title, e.tags)
                ][: batch["limit"]]
                for entry in entries:
                    # Same URL lock used by the ordinary worker. Preserve hidden status.
                    await session.execute(
                        select(func.pg_advisory_xact_lock(func.hashtext(entry.url)))
                    )
                    proposed = uuid4()
                    article_id = (
                        await session.execute(
                            insert(ArticleRow)
                            .values(
                                id=proposed,
                                source_id=source.id,
                                canonical_url=entry.url,
                                title=entry.title,
                                excerpt=entry.excerpt,
                                published_at=published_datetime(entry.published),
                                ingested_at=now,
                                status="published",
                                category=classify_article(entry.title, entry.tags),
                            )
                            .on_conflict_do_nothing(index_elements=["canonical_url"])
                            .returning(ArticleRow.id)
                        )
                    ).scalar_one_or_none()
                    is_new = article_id is not None
                    article = await session.scalar(
                        select(ArticleRow)
                        .where(ArticleRow.canonical_url == entry.url)
                        .with_for_update()
                    )
                    article.title = entry.title
                    article.excerpt = entry.excerpt or article.excerpt
                    article.published_at = (
                        published_datetime(entry.published) or article.published_at
                    )
                    article.category = classify_article(entry.title, entry.tags) or article.category
                    article.ingested_at = article.ingested_at or now
                    if article.status == "legacy":
                        article.status = "published"
                    run.new_articles += int(is_new)
                    run.discovered_urls += 1
                    session.add(
                        ArticleDiscoveryRow(
                            id=uuid4(),
                            run_id=run.id,
                            source_id=source.id,
                            canonical_url=entry.url,
                            original_url=entry.original_url,
                            title=entry.title,
                            published=entry.published,
                            article_id=article.id,
                        )
                    )
                    body = feed["bodies"].get(entry.url)
                    if not body:
                        continue
                    document = parse_document(base64.b64decode(body["html"], validate=True))
                    final_url = canonicalize_url(body["url"])
                    version_id = (
                        await session.execute(
                            insert(ArticleVersionRow)
                            .values(
                                id=uuid4(),
                                article_id=article.id,
                                title=entry.title,
                                source_url=final_url,
                                published_at=article.published_at,
                                paragraphs=document.paragraphs,
                                content_hash=document.content_hash,
                            )
                            .on_conflict_do_nothing(index_elements=["article_id", "content_hash"])
                            .returning(ArticleVersionRow.id)
                        )
                    ).scalar_one_or_none()
                    run.updated_articles += int(version_id is not None and not is_new)
                    if version_id is None:
                        version_id = await session.scalar(
                            select(ArticleVersionRow.id).where(
                                ArticleVersionRow.article_id == article.id,
                                ArticleVersionRow.content_hash == document.content_hash,
                            )
                        )
                    article.current_version_id = version_id
                    article.content_hash = document.content_hash
                    await session.execute(
                        select(func.pg_advisory_xact_lock(func.hashtext(document.content_hash)))
                    )
                    article.duplicate_of_id = await session.scalar(
                        select(ArticleRow.id)
                        .where(
                            ArticleRow.id != article.id,
                            ArticleRow.source_id == article.source_id,
                            ArticleRow.content_hash == document.content_hash,
                            ArticleRow.status.in_(("published", "hidden")),
                            ArticleRow.duplicate_of_id.is_(None),
                        )
                        .order_by(ArticleRow.ingested_at, ArticleRow.id)
                        .limit(1)
                    )
                    run.fetched_articles += 1
                # This is a relay success, not proof of cloud network connectivity.
                if not source.enabled:
                    source.last_checked_at = now
                    source.last_success_at = now
                    source.health = "healthy"
                    source.consecutive_failures = 0
            run.finished_at = datetime.now(UTC)
            run.status = "partial" if errors else "success"
            run.failed_jobs = len(errors)
            run.error_summary = "; ".join(errors)[:2000] or None
            return {
                "id": str(batch_id),
                "new": run.new_articles,
                "updated": run.updated_articles,
                "bodies": run.fetched_articles,
                "warnings": len(errors),
            }
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raw = sys.stdin.buffer.read(100 * 1024 * 1024 + 1)
    if len(raw) > 100 * 1024 * 1024:
        raise SystemExit("batch too large")
    print(json.dumps(asyncio.run(receive(json.loads(raw)))))
