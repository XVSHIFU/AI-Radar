"""Verify the frozen corpus through actual repository/tools on a disposable DB."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_research_quality_seed import CORPUS, ROOT, quality, seed

from radar.postgres_repository import PostgresRepository
from radar.research_guard import ResearchGuard
from radar.research_tools import load_research_skills, research_scope
from radar.schemas import Filters

pytestmark = pytest.mark.postgres


@pytest.fixture
def quality_database(migration_database):
    migration_database.upgrade()
    return migration_database


async def test_seeded_quality_oracles_match_real_repository_and_tools(quality_database):
    connection = await quality_database.connect()
    try:
        report = await seed.seed(connection, quality_database.url.database, CORPUS)
        assert report["counts"]["events"] == 12
        with pytest.raises(ValueError, match="not empty"):
            await seed.seed(connection, quality_database.url.database, CORPUS)
        assert await connection.fetchval("SELECT count(*) FROM events") == 12
        assert await connection.fetchval("SELECT count(*) FROM sources WHERE enabled") == 0
    finally:
        await connection.close()
    engine = create_async_engine(quality_database.rendered_url)
    repository = PostgresRepository(async_sessionmaker(engine, expire_on_commit=False), "test-key")
    skills = load_research_skills(ROOT / "agent/research")
    try:
        ambiguous = await repository.resolve_entities("Orion")
        assert {item.label for item in ambiguous.ambiguous} == {"Orion 公司", "Orion SDK"}
        for case in CORPUS["cases"]:
            filters = Filters.model_validate(case["request"]["filters"])
            page = await repository.list_events(filters, 50, None)
            expected = quality.selected(CORPUS["events"], case["scope"])
            assert page.total == len(expected), case["id"]
            guard = ResearchGuard(uuid4(), "a" * 64, datetime.now(UTC) + timedelta(seconds=90))
            async with research_scope(repository, guard, filters, skills) as tools:
                aggregate = await tools.execute("aggregate_events", {"dimension": "category"})
                assert sum(row["count"] for row in aggregate["rows"]) == len(expected)
                if "counts" in case["required"]:
                    assert {row["category"]: row["count"] for row in aggregate["rows"]} == case[
                        "required"
                    ]["counts"]
                if "first" in case["required"]:
                    comparison = await tools.execute(
                        "compare_periods",
                        {
                            "first": case["periods"][0],
                            "second": case["periods"][1],
                        },
                    )
                    assert [row["count"] for row in comparison["rows"]] == [
                        case["required"]["first"],
                        case["required"]["second"],
                    ]
                    assert comparison["percentage_change"] == case["required"]["increase_percent"]
        # Real saved evidence, UUIDs and paragraphs must match all frozen locators.
        for item in CORPUS["events"]:
            guard = ResearchGuard(uuid4(), "b" * 64, datetime.now(UTC) + timedelta(seconds=90))
            async with research_scope(
                repository, guard, Filters(event_ids=[UUID(item["id"])]), skills
            ) as tools:
                evidence = await tools.execute("get_event_evidence", {"event_ids": [item["id"]]})
                assert {row["citation_id"] for row in evidence["evidence"]} == {
                    row["id"] for row in item["evidence"]
                }
                assert {row["quote_text"] for row in evidence["evidence"]} == {
                    row["quote_text"] for row in item["evidence"]
                }
    finally:
        await engine.dispose()
