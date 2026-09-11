from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from radar.main import app, get_clock

CASES = [
    ("今天", {}, {"date_from": "2026-09-11", "date_to": "2026-09-11"}),
    ("昨天", {}, {"date_from": "2026-09-10", "date_to": "2026-09-10"}),
    ("最近7天", {}, {"date_from": "2026-09-05", "date_to": "2026-09-11"}),
    ("最近一周", {}, {"date_from": "2026-09-05", "date_to": "2026-09-11"}),
    ("本周", {}, {"date_from": "2026-09-07", "date_to": "2026-09-11"}),
    ("上周", {}, {"date_from": "2026-08-31", "date_to": "2026-09-06"}),
    (
        "2026-09-08 至 09-10 的 agent 工具",
        {},
        {"date_from": "2026-09-08", "date_to": "2026-09-10", "category": "agent_tool"},
    ),
    ("model_release", {}, {"category": "model_release"}),
    ("agent_tool", {}, {"category": "agent_tool"}),
    ("framework_sdk", {}, {"category": "framework_sdk"}),
    ("research", {}, {"category": "research"}),
    ("product", {}, {"category": "product"}),
    ("industry", {}, {"category": "industry"}),
]


@pytest.mark.parametrize(("question", "filters", "expected"), CASES)
def test_deterministic_query_plan_cases(
    client: TestClient, question: str, filters: dict, expected: dict
) -> None:
    app.dependency_overrides[get_clock] = lambda: datetime(2026, 9, 11, 4, tzinfo=UTC)
    try:
        response = client.post(
            "/api/v1/query-plan",
            json={
                "question": question,
                "filters": filters,
                "timezone": "Asia/Shanghai",
                "client_request_id": "plan-case",
            },
        )
    finally:
        app.dependency_overrides.pop(get_clock, None)
    assert response.status_code == 200, response.text
    actual = response.json()["filters"]
    for key, value in expected.items():
        assert actual[key] == value


@pytest.mark.parametrize("question", ["DeepSeek", "深度求索", "ＤｅｅｐＳｅｅｋ"])
def test_confirmed_entity_aliases_share_fixture_id(client: TestClient, question: str) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={"question": question, "client_request_id": "entity"},
    )
    assert response.status_code == 200
    assert response.json()["filters"]["entity_ids"] == ["10000000-0000-4000-8000-000000000001"]
    assert response.json()["filters"]["date_from"] is None


@pytest.mark.parametrize(("joiner", "match"), [("或", "any"), ("和", "all")])
def test_entity_boolean_mode(client: TestClient, joiner: str, match: str) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": f"DeepSeek {joiner} 示例研究团队",
            "client_request_id": "entities",
        },
    )
    assert response.status_code == 200
    assert response.json()["filters"]["entity_match"] == match
    assert len(response.json()["filters"]["entity_ids"]) == 2


def test_request_filters_win_with_warning(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "2026-09-08 至 09-10",
            "filters": {"date_from": "2026-09-01", "date_to": "2026-09-02"},
            "client_request_id": "override",
        },
    )
    body = response.json()
    assert body["filters"]["date_from"] == "2026-09-01"
    assert body["filters"]["date_to"] == "2026-09-02"
    assert body["warnings"]


def test_hour_precision_requires_clarification_on_plan_and_ask(client: TestClient) -> None:
    payload = {"question": "过去24小时", "client_request_id": "hours"}
    plan = client.post("/api/v1/query-plan", json=payload)
    answer = client.post("/api/v1/ask", json=payload)
    assert plan.status_code == 200
    assert plan.json()["requires_clarification"] is True
    assert answer.status_code == 422
    assert answer.json()["code"] == "CLARIFICATION_REQUIRED"
    assert answer.json()["details"]["query_plan_public"]["requires_clarification"] is True


def test_invalid_timezone_and_utc_business_boundary(client: TestClient) -> None:
    app.dependency_overrides[get_clock] = lambda: datetime(2026, 9, 10, 16, 30, tzinfo=UTC)
    try:
        utc = client.post(
            "/api/v1/query-plan",
            json={"question": "今天", "timezone": "UTC", "client_request_id": "utc"},
        )
        invalid = client.post(
            "/api/v1/query-plan",
            json={
                "question": "今天",
                "timezone": "Unknown/Nowhere",
                "client_request_id": "bad-zone",
            },
        )
    finally:
        app.dependency_overrides.pop(get_clock, None)
    assert utc.json()["filters"]["date_from"] == "2026-09-10"
    assert invalid.status_code == 422


@pytest.mark.parametrize(
    "question",
    ["2026-02-30 至 03-01", "2026-09-10 至 09-08"],
)
def test_invalid_absolute_ranges_are_validation_errors(client: TestClient, question: str) -> None:
    response = client.post(
        "/api/v1/query-plan", json={"question": question, "client_request_id": "bad-date"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "QUERY_INVALID"


@pytest.mark.parametrize("question", ["今天和昨天", "research 或 product"])
def test_conflicting_inferred_constraints_require_clarification(
    client: TestClient, question: str
) -> None:
    response = client.post(
        "/api/v1/query-plan", json={"question": question, "client_request_id": "conflict"}
    )
    assert response.status_code == 200
    assert response.json()["requires_clarification"] is True
    assert response.json()["warnings"]


def test_mixed_request_and_question_date_is_revalidated(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "2026-09-01 至 09-02",
            "filters": {"date_from": "2026-09-10"},
            "client_request_id": "mixed-date",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "QUERY_INVALID"


def test_unknown_hard_constraint_is_not_treated_as_empty_result(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ask",
        json={
            "question": "DeepSeek 未发布的项目",
            "filters": {"q": "DeepSeek"},
            "client_request_id": "unsupported",
        },
    )
    assert response.status_code == 503
    assert response.json()["code"] == "QUERY_UNSUPPORTED"
    assert response.json()["details"]["query_plan_public"]["free_text"] == "未发布 项目"


@pytest.mark.parametrize(
    ("question", "expected"),
    [("2026-09-09", "2026-09-09"), ("2026-12-31 至 01-02", "2027-01-02")],
)
def test_standalone_and_cross_year_iso_dates(
    client: TestClient, question: str, expected: str
) -> None:
    response = client.post(
        "/api/v1/query-plan", json={"question": question, "client_request_id": "iso-date"}
    )
    assert response.status_code == 200
    assert response.json()["filters"]["date_to"] == expected
    if question == "2026-09-09":
        assert response.json()["filters"]["date_from"] == expected


def test_entity_name_does_not_infer_category_and_request_match_wins(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "DeepSeek 和 示例研究团队",
            "filters": {"entity_match": "any"},
            "client_request_id": "entity-precedence",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["category"] is None
    assert body["filters"]["entity_match"] == "any"
    assert body["warnings"]


def test_maximum_date_returns_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={"question": "9999-12-31", "client_request_id": "max-date"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "QUERY_INVALID"


class DirectoryResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class DirectorySession:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def __call__(self):
        return self

    async def execute(self, _statement):
        return DirectoryResult(self.rows)


@pytest.mark.asyncio
async def test_production_resolver_uses_longest_non_overlapping_confirmed_aliases() -> None:
    from radar.postgres_repository import PostgresRepository

    meta_id = uuid4()
    metaflow_id = uuid4()
    rows = [
        SimpleNamespace(
            id=meta_id,
            canonical_name="Meta",
            aliases=[SimpleNamespace(normalized_alias="meta")],
        ),
        SimpleNamespace(
            id=metaflow_id,
            canonical_name="Metaflow",
            aliases=[SimpleNamespace(normalized_alias="metaflow")],
        ),
    ]
    repository = PostgresRepository(DirectorySession(rows), "secret")

    longest = await repository.resolve_entities("Metaflow")
    explicit_both = await repository.resolve_entities("Meta 和 Metaflow")
    embedded = await repository.resolve_entities("DeepSeeker")

    assert [item.entity_id for item in longest.resolved] == [metaflow_id]
    assert {item.entity_id for item in explicit_both.resolved} == {meta_id, metaflow_id}
    assert embedded.resolved == []


@pytest.mark.parametrize(
    ("question", "category"),
    [("示例研究团队", None), ("示例研究团队的研究", "research")],
)
def test_category_detection_masks_only_confirmed_entity_span(
    client: TestClient, question: str, category: str | None
) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={"question": question, "client_request_id": "entity-category-span"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["category"] == category
    assert body["free_text"] == ""


@pytest.mark.parametrize(
    ("question", "filters", "expected_match"),
    [
        ("DeepSeek 或 示例研究团队", {"entity_match": "all"}, "all"),
        (
            "DeepSeek 和 示例研究团队",
            {
                "entity_ids": ["10000000-0000-4000-8000-000000000001"],
                "entity_match": "any",
            },
            "any",
        ),
    ],
)
def test_explicit_entity_match_always_has_request_origin_and_conflict_warning(
    client: TestClient, question: str, filters: dict, expected_match: str
) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": question,
            "filters": filters,
            "client_request_id": "explicit-match",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["entity_match"] == expected_match
    assert body["constraints_origin"]["entity_match"] == "request"
    assert any("entity_match" in warning for warning in body["warnings"])
