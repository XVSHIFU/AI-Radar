from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.backfill import enqueue
from radar.ingest.core import FeedEntry
from radar.models import (
    ArticleCandidateRow,
    ArticleDiscoveryRow,
    ArticleRow,
    ArticleVersionRow,
    IngestJobRow,
    SourceRow,
)


@pytest.mark.postgres
async def test_history_resume_reuses_frozen_versions_and_deduplicates_shared_jobs(
    postgres_database: Any,
) -> None:
    engine = create_async_engine(postgres_database.url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex
    first = SourceRow(
        id=uuid4(),
        name="history-a-" + suffix,
        feed_url="https://a.example/feed",
        enabled=True,
        canonical_host="a.example",
        channel_type="rss",
    )
    second = SourceRow(
        id=uuid4(),
        name="history-b-" + suffix,
        feed_url="https://b.example/feed",
        enabled=True,
        canonical_host="b.example",
        channel_type="rss",
    )
    saved_url, new_url = f"https://a.example/{suffix}", f"https://shared.example/{suffix}"
    article = ArticleRow(id=uuid4(), source_id=first.id, canonical_url=saved_url)
    version = ArticleVersionRow(
        id=uuid4(),
        article_id=article.id,
        title="Saved",
        source_url=saved_url,
        paragraphs={"p1": "Frozen original."},
        content_hash=suffix.ljust(64, "0"),
    )
    try:
        async with sessions() as session, session.begin():
            session.add_all([first, second])
            await session.flush()
            session.add(article)
            await session.flush()
            session.add(version)
        saved = FeedEntry("Saved", saved_url, saved_url, "2026-08-12T00:00:00Z")
        new = FeedEntry("New", new_url, new_url, "2026-08-13T00:00:00Z")
        selections = [(first, [saved, new]), (second, [saved, new])]
        result = await enqueue(sessions, selections, date(2026, 8, 1), date(2026, 9, 15))
        replay = await enqueue(sessions, selections, date(2026, 8, 1), date(2026, 9, 15))
        assert result["new_jobs"] == 1 and result["new_candidates"] == 2
        assert result["reused_versions"] == 2 and result["new_discoveries"] == 4
        assert replay["run_id"] == result["run_id"]
        assert replay["new_jobs"] == replay["new_candidates"] == replay["new_discoveries"] == 0
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ArticleCandidateRow)
                    .where(
                        ArticleCandidateRow.article_version_id == version.id,
                    )
                )
                == 2
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ArticleDiscoveryRow)
                    .where(
                        ArticleDiscoveryRow.canonical_url.in_([saved_url, new_url]),
                    )
                )
                == 4
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(IngestJobRow)
                    .where(
                        IngestJobRow.payload["canonical_url"].astext == new_url,
                    )
                )
                == 1
            )
        async with sessions() as session, session.begin():
            await session.execute(
                update(IngestJobRow)
                .where(IngestJobRow.payload["canonical_url"].astext == new_url)
                .values(state="failed", last_error="fixture failure")
            )
        failed_replay = await enqueue(sessions, selections, date(2026, 8, 1), date(2026, 9, 15))
        assert failed_replay["status"] == "failed"
        assert failed_replay["new_jobs"] == 0
    finally:
        async with sessions() as session, session.begin():
            for model in (ArticleCandidateRow, ArticleDiscoveryRow, IngestJobRow):
                await session.execute(
                    delete(model).where(model.source_id.in_([first.id, second.id]))
                )
            await session.execute(
                delete(ArticleVersionRow).where(ArticleVersionRow.id == version.id)
            )
            await session.execute(delete(ArticleRow).where(ArticleRow.id == article.id))
            await session.execute(delete(SourceRow).where(SourceRow.id.in_([first.id, second.id])))
        await engine.dispose()
