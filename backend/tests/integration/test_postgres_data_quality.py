import hashlib
import json
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.date_quality import DateQualityService
from radar.event_merge_service import EventMergeService, MergeRejected
from radar.models import EventRow

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_evidence_gated_date_correction_and_reversible_merge(postgres_database) -> None:
    connection = await postgres_database.connect()
    source_id, article_id, version_id = uuid4(), uuid4(), uuid4()
    first, second, third, evidence_id = uuid4(), uuid4(), uuid4(), uuid4()
    quote = "Example AI released Model X on 2026-08-17."
    try:
        await connection.execute(
            "INSERT INTO sources (id,name,feed_url,enabled,health,consecutive_failures,"
            "canonical_host,channel_type) VALUES ($1,$2,'https://example.com/rss',true,"
            "'healthy',0,'example.com','rss')",
            source_id,
            f"quality-{source_id}",
        )
        await connection.execute(
            "INSERT INTO articles (id,source_id,canonical_url) VALUES ($1,$2,$3)",
            article_id,
            source_id,
            f"https://example.com/{article_id}",
        )
        await connection.execute(
            "INSERT INTO article_versions "
            "(id,article_id,title,source_url,paragraphs,content_hash) "
            "VALUES ($1,$2,'Title',$3,$4::jsonb,$5)",
            version_id,
            article_id,
            f"https://example.com/{article_id}",
            json.dumps({"p-1": quote}),
            hashlib.sha256(quote.encode()).hexdigest(),
        )
        for event_id, title in ((first, "事件一"), (second, "事件二"), (third, "事件三")):
            await connection.execute(
                "INSERT INTO events (id,title_zh,summary_zh,category,importance,event_date,"
                "date_precision,date_basis,status,source_count,evidence_count,content_version) "
                "VALUES ($1,$2,'摘要','model_release',3,'2026-09-01','day',"
                "'report_date_unverified','published',1,1,1)",
                event_id,
                title,
            )
        await connection.execute(
            "INSERT INTO evidence (id,event_id,article_version_id,paragraph_id,quote_text,"
            "quote_hash,support_type,verification_status) "
            "VALUES ($1,$2,$3,'p-1',$4,$5,'direct','unverified')",
            evidence_id,
            first,
            version_id,
            quote,
            hashlib.sha256(quote.encode()).hexdigest(),
        )
    finally:
        await connection.close()

    engine = create_async_engine(postgres_database.rendered_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        dates = DateQualityService(sessions)
        candidates = await dates.audit()
        assert next(item for item in candidates if item.event_id == first).status == "candidate"
        await dates.apply(first, evidence_id, date(2026, 8, 17), operator="reviewer")
        async with sessions() as session:
            corrected = await session.get(EventRow, first)
            assert corrected is not None
            assert (corrected.event_date, corrected.date_basis, corrected.date_evidence_id) == (
                date(2026, 8, 17),
                "explicit_body",
                evidence_id,
            )

        merges = EventMergeService(sessions)
        log_id = await merges.merge(
            first,
            second,
            reason="same release confirmed by reviewer",
            evidence={"ticket": "DQ-1"},
            operator="reviewer",
        )
        with pytest.raises(MergeRejected):
            await merges.merge(
                first, second, reason="repeat", evidence={"ticket": "DQ-1"}, operator="reviewer"
            )
        with pytest.raises(MergeRejected, match="merged members"):
            await merges.merge(
                second,
                third,
                reason="attempted chain",
                evidence={"ticket": "DQ-2"},
                operator="reviewer",
            )
        await merges.unmerge(log_id, operator="reviewer-2")
        async with sessions() as session:
            restored = await session.scalar(select(EventRow).where(EventRow.id == first))
            assert restored is not None
            assert restored.status == "published"
            assert restored.merged_into_event_id is None
    finally:
        await engine.dispose()
