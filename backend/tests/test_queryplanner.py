from datetime import UTC, datetime

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
