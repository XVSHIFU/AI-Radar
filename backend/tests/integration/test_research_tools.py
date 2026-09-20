import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.postgres_repository import PostgresRepository
from radar.research_guard import ResearchGuard, ResearchRejected
from radar.research_tools import load_research_skills, research_scope
from radar.schemas import Filters

pytestmark = pytest.mark.postgres


@pytest.fixture
async def data(postgres_database):
    prefix = f"research-{uuid4().hex}"
    ids = [uuid4() for _ in range(11)]
    source, article, version, evidence, entity = (uuid4() for _ in range(5))
    quote = "The new model was released on September 1, 2026."
    connection = await postgres_database.connect()
    try:
        for index, event_id in enumerate(ids):
            title = f"{prefix} item-{index}" if index < 10 else "outside-authorized-scope"
            await connection.execute(
                "INSERT INTO events (id,title_zh,summary_zh,category,importance,event_date,"
                "date_precision,date_basis,status,source_count,evidence_count,content_version,"
                "created_at) VALUES ($1,$2,'original summary',$3,3,$4,$5,$6,"
                "'published',1,1,1,$7)",
                event_id,
                title,
                "model_release" if index < 8 else "product",
                date(2026, 9, 1 if index < 4 else 2) if index != 9 else None,
                "day" if index != 9 else "unknown",
                "official_publication" if index < 8 else "report_date_unverified",
                datetime(2026, 9, 1 if index < 4 else 2 if index < 8 else 3, 12, tzinfo=UTC),
            )
        await connection.execute(
            "INSERT INTO sources (id,name,feed_url,enabled,health,consecutive_failures,"
            "canonical_host,channel_type) VALUES ($1,$2,'https://example.com/feed',true,"
            "'healthy',0,'example.com','rss')",
            source,
            prefix,
        )
        await connection.execute(
            "INSERT INTO articles (id,source_id,canonical_url) VALUES ($1,$2,$3)",
            article,
            source,
            f"https://example.com/{article}",
        )
        await connection.execute(
            "INSERT INTO article_versions (id,article_id,title,source_url,paragraphs,content_hash) "
            "VALUES ($1,$2,'Original title',$3,$4::jsonb,$5)",
            version,
            article,
            f"https://example.com/{article}",
            json.dumps({"p1": quote}),
            hashlib.sha256(quote.encode()).hexdigest(),
        )
        await connection.execute(
            "INSERT INTO evidence (id,event_id,article_version_id,paragraph_id,quote_text,"
            "quote_hash,support_type,verification_status) VALUES ($1,$2,$3,'p1',$4,$5,"
            "'direct','unverified')",
            evidence,
            ids[0],
            version,
            quote,
            hashlib.sha256(quote.encode()).hexdigest(),
        )
        await connection.execute(
            "INSERT INTO entities (id,canonical_name,entity_type) VALUES ($1,$2,'company')",
            entity,
            f"company-{prefix}",
        )
        await connection.execute(
            "INSERT INTO entity_aliases (id,entity_id,normalized_alias,alias_source) "
            "VALUES ($1,$2,$3,'curated')",
            uuid4(),
            entity,
            prefix,
        )
        await connection.execute(
            "INSERT INTO event_entities (event_id,entity_id,role) VALUES ($1,$2,'subject')",
            ids[0],
            entity,
        )
    finally:
        await connection.close()
    engine = create_async_engine(postgres_database.rendered_url)
    repository = PostgresRepository(async_sessionmaker(engine, expire_on_commit=False), "test-key")
    # q uses exact entity aliases preferentially. A prefix distinct from the alias
    # deliberately exercises text-filter scope across all ten seeded events.
    filters = Filters(q=prefix + " item")
    skills = load_research_skills(Path(__file__).resolve().parents[3] / "agent/research")
    try:
        yield repository, filters, skills, ids, evidence, version, prefix, postgres_database
    finally:
        await engine.dispose()


def guard():
    return ResearchGuard(uuid4(), "a" * 64, datetime.now(UTC) + timedelta(seconds=90))


async def test_snapshot_keeps_counts_search_and_evidence_consistent_during_writes(data):
    repository, filters, skills, ids, evidence, version, prefix, db = data
    async with research_scope(repository, guard(), filters, skills) as tools:
        page = await tools.execute("search_events", {})
        assert page["scope_total"] == page["matched_total"] == 10
        assert page["returned_count"] == 6 and page["next_cursor"] and not page["complete"]
        aggregate = await tools.execute("aggregate_events", {"dimension": "category"})
        assert aggregate["total_items"] == 10
        assert aggregate["total_articles"] == 0
        assert aggregate["total_curated_events"] == 10
        assert sum(row["count"] for row in aggregate["rows"]) == 10
        first_evidence = await tools.execute("get_event_evidence", {"event_ids": [str(ids[0])]})
        assert first_evidence["evidence"][0]["citation_id"] == str(evidence)
        connection = await db.connect()
        try:
            await connection.execute("UPDATE events SET summary_zh='changed' WHERE id=$1", ids[0])
            await connection.execute(
                "UPDATE article_versions SET title='Changed after snapshot' WHERE id=$1",
                version,
            )
            await connection.execute("UPDATE events SET status='rejected' WHERE id=$1", ids[1])
        finally:
            await connection.close()
        after = await tools.execute("search_events", {"query": "item-0"})
        assert after["events"][0]["excerpt"] == "original summary"
        assert after["scope_total"] == 10
        second_evidence = await tools.execute("get_event_evidence", {"event_ids": [str(ids[0])]})
        assert second_evidence == first_evidence
        next_page = await tools.execute("search_events", {"cursor": page["next_cursor"]})
        assert next_page["returned_count"] == 4 and next_page["next_cursor"] is None
        assert not ({x["id"] for x in page["events"]} & {x["id"] for x in next_page["events"]})
        chart = await tools.execute(
            "build_chart", {"dataset_id": aggregate["dataset_id"], "kind": "bar"}
        )
        assert chart["dataset"]["rows"] == aggregate["rows"]
        assert chart["dataset"]["scope_id"] == page["scope_id"]
    async with research_scope(repository, guard(), filters, skills) as later:
        assert (await later.execute("search_events", {}))["scope_total"] == 9


async def test_out_of_scope_ids_datasets_cursors_and_expired_runs_are_rejected(data):
    repository, filters, skills, ids, *_ = data
    first_guard = guard()
    async with research_scope(repository, first_guard, filters, skills) as first:
        page = await first.execute("search_events", {})
        dataset = await first.execute("aggregate_events", {"dimension": "category"})
        with pytest.raises(ResearchRejected, match="NOT_FOUND"):
            await first.execute("get_event_evidence", {"event_ids": [str(ids[0]), str(ids[10])]})
        assert first.citations == {}
        with pytest.raises(ResearchRejected, match="INVALID_ARGUMENT"):
            await first.execute(
                "search_events", {"cursor": page["next_cursor"], "query": "changed"}
            )
        async with research_scope(repository, guard(), filters, skills) as second:
            with pytest.raises(ResearchRejected, match="NOT_FOUND"):
                await second.execute(
                    "build_chart", {"dataset_id": dataset["dataset_id"], "kind": "bar"}
                )
            with pytest.raises(ResearchRejected, match="INVALID_ARGUMENT"):
                await second.execute("search_events", {"cursor": page["next_cursor"]})
        first_guard.close()
        with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
            await first.execute("search_events", {})
    with pytest.raises(ResearchRejected, match="RUN_EXPIRED"):
        await second.execute("search_events", {})


async def test_exact_dates_zero_baseline_scope_limits_and_scoped_skills(data):
    repository, filters, skills, ids, _, _, prefix, _ = data
    run = guard()
    async with research_scope(repository, run, filters, skills) as tools:
        dates = await tools.execute("aggregate_events", {"dimension": "date"})
        assert dates["included_items"] == 10 and dates["excluded_unknown_dates"] == 0
        assert dates["date_basis"] == "event_date_or_source_publication_or_collection_date"
        # The ninth item has a stored September 2 date despite September 3 collection.
        assert dates["rows"] == [
            {"date": "2026-09-01", "count": 4},
            {"date": "2026-09-02", "count": 5},
            {"date": "2026-09-03", "count": 1},
        ]
        comparison = await tools.execute(
            "compare_periods",
            {
                "first": {"from": "2026-08-01", "to": "2026-08-31"},
                "second": {"from": "2026-09-01", "to": "2026-09-02"},
            },
        )
        assert comparison["zero_baseline"] and comparison["percentage_change"] is None
        assert comparison["difference"] == 9 and comparison["unequal_duration"]
        assert comparison["coverage_gaps"] == "not_measured"
        assert (await tools.execute("resolve_entities", {"name": prefix}))["matches"]
        skill = await tools.execute("load_research_skill", {"name": "compare-periods"})
        assert "零" in skill["body"] and len(skill["version"]) == 64
        with pytest.raises(ResearchRejected, match="TOOL_UNAVAILABLE"):
            await tools.execute("shell", {"command": "id"})
    bounded = Filters(q=filters.q, date_from=date(2026, 9, 1), date_to=date(2026, 9, 2))
    async with research_scope(repository, guard(), bounded, skills) as tools:
        with pytest.raises(ResearchRejected, match="SCOPE_CHANGE_REQUIRED"):
            await tools.execute(
                "compare_periods",
                {
                    "first": {"from": "2026-08-01", "to": "2026-08-31"},
                    "second": {"from": "2026-09-01", "to": "2026-09-02"},
                },
            )
        assert (await tools.execute("search_events", {}))["scope_total"] == 9


async def test_database_enforces_read_only_even_for_accidental_write(data):
    repository, filters, skills, ids, *_ = data
    with pytest.raises(DBAPIError, match="read-only"):
        async with research_scope(repository, guard(), filters, skills) as tools:
            await tools.session.execute(
                text("UPDATE events SET importance=1 WHERE id=:id"), {"id": ids[0]}
            )


async def test_changed_quote_hash_cannot_become_a_citation(data):
    repository, filters, skills, ids, evidence, _, _, db = data
    connection = await db.connect()
    try:
        await connection.execute(
            "UPDATE evidence SET quote_hash=$1 WHERE id=$2", "0" * 64, evidence
        )
    finally:
        await connection.close()
    async with research_scope(repository, guard(), filters, skills) as tools:
        with pytest.raises(ResearchRejected, match="TOOL_UNAVAILABLE"):
            await tools.execute("get_event_evidence", {"event_ids": [str(ids[0])]})
        assert tools.citations == {}
