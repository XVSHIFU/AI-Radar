from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError


def test_date_bounds_are_inclusive(client: TestClient) -> None:
    response = client.get(
        "/api/v1/events", params={"date_from": "2026-09-08", "date_to": "2026-09-10", "limit": 100}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 15
    assert {item["event_date"] for item in body["items"]} == {
        "2026-09-08",
        "2026-09-09",
        "2026-09-10",
    }
    assert body["total_relation"] == "eq"


def test_pagination_union_total_and_no_duplicates(client: TestClient) -> None:
    ids: list[str] = []
    cursor = None
    totals = set()
    while True:
        params = {"limit": 7}
        if cursor:
            params["cursor"] = cursor
        body = client.get("/api/v1/events", params=params).json()
        totals.add(body["total"])
        ids.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert totals == {32}
    assert len(ids) == len(set(ids)) == 32


def test_cursor_is_bound_to_filters_and_signed(client: TestClient) -> None:
    cursor = client.get("/api/v1/events", params={"limit": 2}).json()["next_cursor"]
    reused = client.get(
        "/api/v1/events", params={"limit": 2, "category": "research", "cursor": cursor}
    )
    tampered = client.get("/api/v1/events", params={"limit": 2, "cursor": cursor[:-1] + "A"})
    assert reused.status_code == 422
    assert reused.json()["code"] == "INVALID_CURSOR"
    assert tampered.status_code == 422


def test_deepseek_aliases_match_subject_without_embedding(client: TestClient) -> None:
    expected = {
        item["id"]
        for item in client.get("/api/v1/events", params={"q": "DeepSeek", "limit": 100}).json()[
            "items"
        ]
    }
    assert len(expected) == 6
    for alias in ("deepseek", "深度求索"):
        body = client.get("/api/v1/events", params={"q": alias, "limit": 100}).json()
        assert {item["id"] for item in body["items"]} == expected
    assert all(
        item["entities"] == ["DeepSeek"]
        for item in client.get("/api/v1/events", params={"q": "DeepSeek"}).json()["items"]
    )


def test_evidence_is_locatable_in_synthetic_article_version(client: TestClient) -> None:
    event_id = "00000000-0000-4000-8000-000000000002"
    detail = client.get(f"/api/v1/events/{event_id}").json()
    evidence = detail["evidence"][0]
    assert detail["data_mode"] == "fixture"
    assert detail["articles"][0]["synthetic"] is True
    assert evidence["quote_text"] == detail["articles"][0]["paragraphs"][evidence["paragraph_id"]]
    missing = client.get("/api/v1/events/00000000-0000-4000-8000-000000000001/evidence").json()
    assert missing["items"] == []


def test_no_answer_is_distinct_from_model_failure(client: TestClient) -> None:
    no_answer = client.post(
        "/api/v1/ask",
        json={
            "question": "查这个明确关键词",
            "filters": {"q": "绝对不存在的合成事件"},
            "client_request_id": "a",
        },
    )
    assert no_answer.status_code == 200
    assert no_answer.json()["answer_status"] == "no_answer"
    unavailable = client.post(
        "/api/v1/ask", json={"question": "DeepSeek", "client_request_id": "b"}
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "MODEL_UNAVAILABLE"


def test_admin_requires_credentials(client: TestClient) -> None:
    denied = client.post("/api/v1/ingest/runs")
    assert denied.status_code == 503
    assert denied.json()["code"] == "MANAGEMENT_UNAVAILABLE"


def test_validation_errors(client: TestClient) -> None:
    assert client.get("/api/v1/events", params={"category": "made_up"}).status_code == 422
    inverted = client.get(
        "/api/v1/events", params={"date_from": "2026-09-11", "date_to": "2026-09-08"}
    )
    assert inverted.status_code == 422
    assert inverted.json()["code"] == "INVALID_DATE_RANGE"


def test_unparsed_natural_language_is_not_reported_as_no_answer(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ask",
        json={"question": "请随便说说最近趋势", "client_request_id": "unparsed"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_UNAVAILABLE"


def test_unknown_evidence_event_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/events/99999999-0000-4000-8000-000000000001/evidence")
    assert response.status_code == 404
    assert response.json()["code"] == "EVENT_NOT_FOUND"


def test_fixture_ready_is_explicitly_not_postgres(client: TestClient) -> None:
    body = client.get("/health/ready").json()
    assert body["status"] == "fixture_ready"
    assert body["postgres_ready"] is False
    assert body["synthetic"] is True


def test_validation_error_has_uniform_shape(client: TestClient) -> None:
    body = client.get("/api/v1/events", params={"category": "invalid"}).json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["retryable"] is False
    assert body["request_id"]
    assert body["details"]["errors"]


def test_query_and_entity_filter_both_apply(client: TestClient) -> None:
    team_id = "10000000-0000-4000-8000-000000000002"
    body = client.get(
        "/api/v1/events",
        params={"q": "MCP", "entity_ids": team_id, "limit": 100},
    ).json()
    assert body["total"] == 5
    assert all("MCP" in item["title_zh"] for item in body["items"])


def test_configured_admin_rejects_bad_token_without_fake_success(client: TestClient) -> None:
    client.app.state.settings.admin_token = "secret"
    denied = client.post("/api/v1/ingest/runs")
    wrong = client.post("/api/v1/ingest/runs", headers={"Authorization": "Bearer wrong"})
    accepted_auth = client.post(
        "/api/v1/ingest/runs",
        headers={
            "Authorization": "Bearer secret",
            "Idempotency-Key": "fixture-disabled",
        },
        json={"source_ids": ["10000000-0000-4000-8000-000000000001"]},
    )
    assert denied.status_code == wrong.status_code == 401
    assert accepted_auth.status_code == 503
    assert accepted_auth.json()["code"] == "INGEST_NOT_AVAILABLE"


def test_ask_rejects_inverted_date_range(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ask",
        json={
            "question": "指定范围",
            "filters": {
                "date_from": "2026-09-11",
                "date_to": "2026-09-08",
            },
            "client_request_id": "bad-range",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


class BrokenIngestRepository:
    async def runs(self):
        raise SQLAlchemyError("database offline")


def test_ingest_database_error_has_uniform_503_shape(client: TestClient) -> None:
    client.app.state.settings.admin_token = "secret"
    client.app.state.ingest_repository = BrokenIngestRepository()
    response = client.get("/api/v1/ingest/runs", headers={"Authorization": "Bearer secret"})

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "DATABASE_UNAVAILABLE"
    assert body["retryable"] is True
    assert body["request_id"]
