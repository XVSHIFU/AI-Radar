"""Greenfield acceptance: fixed query plans must produce the exact paginated scope."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from radar.fixture_repository import FixtureRepository
from radar.main import app, get_clock, get_repository
from radar.queryplanner import ResolvedEntity, resolve_confirmed_entities


@pytest.mark.parametrize(
    ("case_id", "question", "clock", "zone", "start", "end"),
    [
        ("T04", "今天", "2026-09-10T16:30:00+00:00", "Asia/Shanghai", "2026-09-11", "2026-09-11"),
        ("T05", "昨天", "2027-01-01T04:00:00+00:00", "Asia/Shanghai", "2026-12-31", "2026-12-31"),
        ("T05", "昨天", "2026-03-01T04:00:00+00:00", "Asia/Shanghai", "2026-02-28", "2026-02-28"),
        (
            "T06",
            "最近7天",
            "2026-09-11T04:00:00+00:00",
            "Asia/Shanghai",
            "2026-09-05",
            "2026-09-11",
        ),
        ("T07", "本周", "2026-09-11T04:00:00+00:00", "Asia/Shanghai", "2026-09-07", "2026-09-11"),
        ("T08", "上周", "2026-09-11T04:00:00+00:00", "Asia/Shanghai", "2026-08-31", "2026-09-06"),
        ("T09", "今天", "2026-09-10T16:30:00+00:00", "UTC", "2026-09-10", "2026-09-10"),
    ],
)
def test_relative_plan_exact_event_ids(
    client: TestClient,
    tmp_path: Path,
    case_id: str,
    question: str,
    clock: str,
    zone: str,
    start: str,
    end: str,
) -> None:
    left, right = datetime.fromisoformat(start), datetime.fromisoformat(end)
    days = (right - left).days
    items = [
        {
            "id": str(UUID(int=index + 100)),
            "title_zh": f"边界事件 {index}",
            "summary_zh": "合成验收事件",
            "category": "model_release",
            "importance": 3,
            "event_date": (left + timedelta(days=index - 1)).date().isoformat(),
            "date_precision": "day",
            "date_basis": "explicit_body",
            "entities": [],
            "source_count": 0,
            "evidence_count": 0,
            "content_version": 1,
        }
        for index in range(days + 3)
    ]
    fixture = tmp_path / "events.json"
    fixture.write_text(json.dumps({"dataset": "greenfield-boundaries", "items": items}))
    repo = FixtureRepository(fixture, "boundary-cursor-secret")
    fixed = datetime.fromisoformat(clock)
    app.dependency_overrides[get_clock] = lambda: fixed
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        plan = client.post(
            "/api/v1/query-plan",
            json={
                "question": question,
                "timezone": zone,
                "client_request_id": case_id,
            },
        )
        assert plan.status_code == 200
        filters = plan.json()["filters"]
        assert (filters["date_from"], filters["date_to"]) == (start, end)
        assert plan.json()["requires_clarification"] is False
        seen: list[str] = []
        cursor = None
        for _ in range(days + 3):
            params = {"date_from": start, "date_to": end, "limit": 2}
            if cursor is not None:
                params["cursor"] = cursor
            response = client.get("/api/v1/events", params=params)
            assert response.status_code == 200
            page = response.json()
            assert page["total"] == days + 1
            seen.extend(row["id"] for row in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert cursor is None
        assert len(seen) == len(set(seen)) == days + 1
        assert set(seen) == {str(UUID(int=index + 100)) for index in range(1, days + 2)}
    finally:
        app.dependency_overrides.pop(get_clock, None)
        app.dependency_overrides.pop(get_repository, None)


def test_e08_ambiguous_and_fuzzy_entities_are_not_silently_confirmed() -> None:
    first = ResolvedEntity("Acme AI", UUID(int=41))
    second = ResolvedEntity("Acme Cloud", UUID(int=42))
    ambiguous = resolve_confirmed_entities("acme", {"acme": [first, second]})
    assert ambiguous.resolved == []
    assert {item.entity_id for item in ambiguous.ambiguous} == {first.entity_id, second.entity_id}
    fuzzy = resolve_confirmed_entities("deepsek", {"deepseek": [first]})
    assert fuzzy.resolved == [] and fuzzy.ambiguous == [first]
