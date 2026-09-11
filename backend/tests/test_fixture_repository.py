from pathlib import Path
from uuid import UUID

import pytest

from radar.fixture_repository import FixtureRepository
from radar.schemas import Filters

FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "prototype-not-used.json"


def item(number: int, title: str, importance: int, entities: list[str]) -> dict[str, object]:
    return {
        "id": f"50000000-0000-4000-8000-{number:012d}",
        "title_zh": title,
        "summary_zh": "合成测试摘要",
        "category": "research",
        "importance": importance,
        "event_date": "2026-09-12",
        "date_precision": "day",
        "source_count": 0,
        "evidence_count": 0,
        "entities": entities,
        "content_version": 1,
    }


@pytest.mark.asyncio
async def test_explicit_empty_fixture_stays_empty(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text('{"dataset":"test","items":[{"unused":true}]}', encoding="utf-8")
    repository = FixtureRepository(fixture, "secret-secret-secret", items=[])
    page = await repository.list_events(Filters(), 20, None)
    assert page.total == 0
    assert page.items == []


@pytest.mark.asyncio
async def test_entity_alias_does_not_match_title_only_mention(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text('{"dataset":"test","items":[]}', encoding="utf-8")
    repository = FixtureRepository(
        fixture,
        "secret-secret-secret",
        items=[
            item(1, "DeepSeek 主体发布", 3, ["DeepSeek"]),
            item(2, "与 DeepSeek 对比的其他研究", 5, ["示例研究团队"]),
        ],
    )
    page = await repository.list_events(Filters(q="DeepSeek"), 20, None)
    assert [event.title_zh for event in page.items] == ["DeepSeek 主体发布"]


@pytest.mark.asyncio
async def test_headlines_rank_all_today_events_before_limit(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text('{"dataset":"test","items":[]}', encoding="utf-8")
    repository = FixtureRepository(
        fixture,
        "secret-secret-secret",
        items=[
            item(1, "最高重要度但最小 ID", 5, ["示例研究团队"]),
            item(2, "普通二", 2, ["示例研究团队"]),
            item(3, "普通三", 3, ["示例研究团队"]),
            item(4, "普通四", 4, ["示例研究团队"]),
        ],
    )
    headlines = (await repository.insights())["headlines"]
    ids = {event.id for event in headlines}
    assert UUID("50000000-0000-4000-8000-000000000001") in ids
    assert len(ids) == 3
