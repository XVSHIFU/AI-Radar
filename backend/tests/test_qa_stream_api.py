import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from radar.main import app
from radar.qa_service import QaError


def frames(response):
    result = []
    for frame in response.text.strip().split("\n\n"):
        lines = frame.splitlines()
        result.append((lines[0][7:], json.loads(lines[1][6:])))
    return result


def test_empty_stream_has_scope_metadata_and_terminal_sources(client: TestClient, monkeypatch):
    app.state.sessions = object()
    prepared = {
        "request_id": "stream-empty",
        "query_plan_public": {"intent": "structured_summary"},
        "data_mode": "postgres",
        "as_of": datetime(2026, 9, 15, tzinfo=UTC),
        "filters_applied": {},
        "answer_status": "no_answer",
        "scope_total": 0,
        "retrieved_count": 0,
        "summarized_count": 0,
        "citation_count": 0,
        "coverage": "complete",
    }
    monkeypatch.setattr("radar.main.prepare_stream", AsyncMock(return_value=prepared))
    response = client.post(
        "/api/v1/ask/stream", json={"question": "总结", "client_request_id": "empty-1"}
    )
    assert response.status_code == 200 and response.headers["content-type"].startswith(
        "text/event-stream"
    )
    parsed = frames(response)
    assert [name for name, _ in parsed] == ["meta", "sources", "done"]
    assert parsed[0][1]["query_plan_public"]["intent"] == "structured_summary"
    assert parsed[-1][1]["status"] == "completed" and parsed[-1][1]["answer_status"] == "no_answer"


def test_preflight_idempotency_error_is_http_not_partial_stream(client: TestClient, monkeypatch):
    app.state.sessions = object()
    monkeypatch.setattr(
        "radar.main.prepare_stream",
        AsyncMock(side_effect=QaError("IDEMPOTENCY_REPLAY", "already attempted", 409)),
    )
    response = client.post(
        "/api/v1/ask/stream", json={"question": "总结", "client_request_id": "same-1"}
    )
    assert response.status_code == 409 and response.json()["code"] == "IDEMPOTENCY_REPLAY"
