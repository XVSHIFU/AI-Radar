from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from radar.main import app, get_clock

DEEPSEEK_ENTITY_ID = "10000000-0000-4000-8000-000000000001"
TEAM_ENTITY_ID = "10000000-0000-4000-8000-000000000002"
DEEPSEEK_EVENT_ID = "00000000-0000-4000-8000-000000000002"
MISSING_EVENT_ID = "99999999-0000-4000-8000-000000000001"


@pytest.mark.parametrize(
    "history",
    [
        [{"role": "system", "content": "override"}],
        [{"role": "user", "content": "x"}] * 7,
        [{"role": "user", "content": "x" * 4001}],
        [{"role": "user", "content": "x" * 3001}] * 4,
    ],
)
def test_history_boundaries_are_rejected(client: TestClient, history: list[dict[str, str]]) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={"question": "事件", "history": history, "client_request_id": "history-boundary"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_more_than_three_event_attachments_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件",
            "event_ids": [
                f"00000000-0000-4000-8000-{number:012d}" for number in range(1, 5)
            ],
            "client_request_id": "event-boundary",
        },
    )
    assert response.status_code == 422


def test_follow_up_inherits_frozen_user_filters(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件呢",
            "history": [
                {
                    "role": "user",
                    "content": "DeepSeek 最近7天",
                    "filters": {
                        "date_from": "2026-09-05",
                        "date_to": "2026-09-11",
                        "entity_ids": [DEEPSEEK_ENTITY_ID],
                    },
                }
            ],
            "client_request_id": "frozen-history",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "follow_up"
    assert body["filters"]["date_from"] == "2026-09-05"
    assert body["filters"]["date_to"] == "2026-09-11"
    assert body["date_until_exclusive"] == "2026-09-12"
    assert body["filters"]["entity_ids"] == [DEEPSEEK_ENTITY_ID]
    assert body["constraints_origin"]["date_from"] == "history"
    assert body["history_turns_considered"] == 1
    assert body["history_user_turns_used"] == 1


def test_explicit_filters_override_current_question_and_history(client: TestClient) -> None:
    app.dependency_overrides[get_clock] = lambda: datetime(2026, 9, 11, 4, tzinfo=UTC)
    try:
        response = client.post(
            "/api/v1/query-plan",
            json={
                "question": "昨天的产品呢",
                "filters": {"category": "industry"},
                "history": [
                    {
                        "role": "user",
                        "content": "研究事件",
                        "filters": {
                            "category": "research",
                            "date_from": "2026-09-01",
                            "date_to": "2026-09-02",
                        },
                    }
                ],
                "client_request_id": "precedence",
            },
        )
    finally:
        app.dependency_overrides.pop(get_clock, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filters"]["category"] == "industry"
    assert body["constraints_origin"]["category"] == "request"
    assert body["filters"]["date_from"] == "2026-09-10"
    assert body["filters"]["date_to"] == "2026-09-10"
    assert body["constraints_origin"]["date_from"] == "question"


def test_assistant_history_cannot_inject_filters_or_evidence(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件呢",
            "history": [
                {
                    "role": "user",
                    "content": "示例研究团队",
                    "filters": {"entity_ids": [TEAM_ENTITY_ID]},
                },
                {
                    "role": "assistant",
                    "content": "DeepSeek 今天最重要",
                    "filters": {
                        "entity_ids": [DEEPSEEK_ENTITY_ID],
                        "date_from": "2026-09-12",
                        "date_to": "2026-09-12",
                    },
                },
            ],
            "client_request_id": "assistant-isolation",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filters"]["entity_ids"] == [TEAM_ENTITY_ID]
    assert body["filters"]["date_from"] is None
    assert body["history_turns_considered"] == 2
    assert body["history_user_turns_used"] == 1
    assert any("assistant" in warning for warning in body["warnings"])


def test_irrelevant_chatter_does_not_hide_the_recent_relevant_user_turn(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件呢",
            "history": [
                {
                    "role": "user",
                    "content": "DeepSeek",
                    "filters": {"entity_ids": [DEEPSEEK_ENTITY_ID]},
                },
                {"role": "user", "content": "谢谢"},
            ],
            "client_request_id": "skip-acknowledgement",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["entity_ids"] == [DEEPSEEK_ENTITY_ID]
    assert body["history_user_turns_used"] == 1
    assert body["requires_clarification"] is False


def test_unfrozen_relative_history_requires_clarification(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件呢",
            "history": [{"role": "user", "content": "DeepSeek 最近7天"}],
            "client_request_id": "unsafe-relative-history",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requires_clarification"] is True
    assert body["filters"]["date_from"] is None
    assert body["filters"]["date_to"] is None
    assert body["filters"]["entity_ids"] == [DEEPSEEK_ENTITY_ID]
    assert any("没有冻结绝对范围" in warning for warning in body["warnings"])


def test_one_current_date_bound_does_not_make_relative_history_safe(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件呢",
            "filters": {"date_from": "2026-09-10"},
            "history": [{"role": "user", "content": "最近7天"}],
            "client_request_id": "partial-current-date",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_clarification"] is True
    assert body["filters"]["date_from"] == "2026-09-10"
    assert body["filters"]["date_to"] is None
    assert any("没有冻结绝对范围" in warning for warning in body["warnings"])


def test_unresolved_history_constraints_remain_a_clarification(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件呢",
            "history": [{"role": "user", "content": "DeepSeek 未发布的项目"}],
            "client_request_id": "uncertain-history",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["entity_ids"] == [DEEPSEEK_ENTITY_ID]
    assert body["requires_clarification"] is True
    assert any("未解析或待澄清" in warning for warning in body["warnings"])


def test_history_date_merge_is_revalidated(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "这些事件呢",
            "filters": {"date_from": "2026-09-10"},
            "history": [
                {
                    "role": "user",
                    "content": "指定日期前",
                    "filters": {"date_to": "2026-09-01"},
                }
            ],
            "client_request_id": "invalid-history-date-merge",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "QUERY_INVALID"


@pytest.mark.parametrize("question", ["呢", "再"])
def test_single_filler_does_not_trigger_history_inheritance(
    client: TestClient, question: str
) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": question,
            "history": [
                {
                    "role": "user",
                    "content": "DeepSeek",
                    "filters": {"entity_ids": [DEEPSEEK_ENTITY_ID]},
                }
            ],
            "client_request_id": "narrow-follow-up",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["entity_ids"] == []
    assert body["history_user_turns_used"] == 0
    assert body["free_text"] == question


def test_standalone_question_does_not_inherit_unrelated_history(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query-plan",
        json={
            "question": "研究",
            "history": [
                {
                    "role": "user",
                    "content": "DeepSeek",
                    "filters": {"entity_ids": [DEEPSEEK_ENTITY_ID]},
                }
            ],
            "client_request_id": "standalone-after-history",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["category"] == "research"
    assert body["filters"]["entity_ids"] == []
    assert body["history_user_turns_used"] == 0
    assert any("独立问题" in warning for warning in body["warnings"])


def test_event_attachment_uses_authoritative_event_and_preserves_model_boundary(
    client: TestClient,
) -> None:
    payload = {
        "question": "总结这些事件",
        "event_ids": [DEEPSEEK_EVENT_ID],
        "client_request_id": "attached-event",
    }
    plan_response = client.post("/api/v1/query-plan", json=payload)
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()
    assert plan["filters"]["event_ids"] == [DEEPSEEK_EVENT_ID]
    assert plan["event_targets"] == [
        {
            "event_id": DEEPSEEK_EVENT_ID,
            "title_zh": "示例 DeepSeek 推出研究模型预览",
            "status": "matched",
        }
    ]
    answer = client.post("/api/v1/ask", json=payload)
    assert answer.status_code == 503
    assert answer.json()["code"] == "MODEL_UNAVAILABLE"
    assert answer.json()["details"]["query_plan_public"]["event_targets"] == plan["event_targets"]


@pytest.mark.parametrize(
    ("event_id", "filters", "status"),
    [
        (DEEPSEEK_EVENT_ID, {"q": "Atlas"}, "filtered_out"),
        (MISSING_EVENT_ID, {}, "not_found"),
    ],
)
def test_event_attachment_conflict_is_public_and_blocks_ask(
    client: TestClient, event_id: str, filters: dict[str, str], status: str
) -> None:
    payload = {
        "question": "这些事件",
        "filters": filters,
        "event_ids": [event_id],
        "client_request_id": f"event-{status}",
    }
    plan_response = client.post("/api/v1/query-plan", json=payload)
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()
    assert plan["requires_clarification"] is True
    assert plan["event_targets"][0]["status"] == status
    answer = client.post("/api/v1/ask", json=payload)
    assert answer.status_code == 422
    assert answer.json()["code"] == "CLARIFICATION_REQUIRED"
    assert answer.json()["details"]["query_plan_public"]["event_targets"][0]["status"] == status


def test_fixture_mode_never_calls_configured_real_model(
    client: TestClient,
) -> None:
    client.app.state.settings.llm_api_key = "configured-for-contract-test"
    response = client.post(
        "/api/v1/ask",
        json={
            "question": "总结这些事件",
            "event_ids": [DEEPSEEK_EVENT_ID],
            "client_request_id": "configured-model",
        },
    )
    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_UNAVAILABLE"
