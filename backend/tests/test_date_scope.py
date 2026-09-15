from datetime import date
from pathlib import Path

import pytest

from radar.fixture_repository import FixtureRepository
from radar.schemas import Filters


@pytest.mark.asyncio
async def test_date_scope_excludes_unverified_and_conflicted_dates(tmp_path: Path) -> None:
    rows = []
    for index, (basis, conflict) in enumerate(
        (
            ("explicit_body", False),
            ("official_publication", False),
            ("report_date_unverified", False),
            ("explicit_body", True),
        ),
        start=1,
    ):
        rows.append(
            {
                "id": f"50000000-0000-4000-8000-{index:012d}",
                "title_zh": "合成日期验收",
                "summary_zh": "仅用于日期范围回归。",
                "category": "research",
                "importance": 3,
                "event_date": "2026-09-10",
                "date_precision": "day",
                "date_basis": basis,
                "date_conflict": conflict,
                "source_count": 0,
                "evidence_count": 0,
                "entities": [],
                "content_version": 1,
            }
        )
    fixture = tmp_path / "fixture.json"
    fixture.write_text('{"dataset":"synthetic-date-scope","items":[]}', encoding="utf-8")
    repository = FixtureRepository(fixture, "test-cursor-secret", items=rows)
    all_events = await repository.list_events(Filters(), 20, None)
    strict = await repository.list_events(Filters(date_from=date(2026, 9, 10)), 20, None)
    assert all_events.total == 4
    assert strict.total == 2
    assert all(
        event.date_basis != "report_date_unverified" and not event.date_conflict
        for event in strict.items
    )
