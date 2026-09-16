from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from radar.main import app
from radar.public_assistant import COOKIE, PublicRun
from radar.public_identity import PublicIdentity
from radar.public_quota import PublicAdmissionError, PublicReservation, QuotaSnapshot
from radar.qa_service import QaError


@pytest.fixture
def metered(client, monkeypatch):
    app.state.settings = app.state.settings.model_copy(update={"radar_data_mode": "postgres"})
    app.state.sessions = object()
    identity = PublicIdentity("test-private-signing-secret-123456789")
    quota = AsyncMock()
    quota.snapshot.return_value = QuotaSnapshot(5, 5, None)
    quota.reserve.return_value = PublicReservation(
        uuid4(), datetime.now(UTC) + timedelta(seconds=90), QuotaSnapshot(4, 5, None)
    )
    app.state.public_identity = identity
    app.state.public_quota = quota
    # TestClient's peer name is not an IP; provide a concrete trusted transport peer.
    monkeypatch.setattr("radar.public_assistant.private_ip", lambda _r, i: i.ip_key("192.0.2.4"))
    monkeypatch.setattr(PublicRun, "finish", AsyncMock())
    return client, identity, quota


def test_session_is_private_and_new_cookie_does_not_reset_ip_quota(metered):
    client, identity, quota = metered
    first = client.get("/api/v1/assistant/session")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert "HttpOnly" in first.headers["set-cookie"]
    assert "SameSite=lax" in first.headers["set-cookie"]
    owner = identity.subject(client.cookies.get(COOKIE))
    assert owner and owner not in first.text and "token" not in first.text
    client.cookies.clear()
    quota.snapshot.return_value = QuotaSnapshot(3, 5, None)
    second = client.get("/api/v1/assistant/session")
    assert second.json()["quota"]["remaining"] == 3
    assert identity.subject(client.cookies.get(COOKIE)) != owner
    assert quota.snapshot.await_args_list[0] == quota.snapshot.await_args_list[1]


@pytest.mark.parametrize("path", ["/api/v1/ask", "/api/v1/ask/stream"])
def test_missing_session_blocks_both_paid_endpoints(metered, monkeypatch, path):
    client, _, quota = metered
    paid = AsyncMock()
    monkeypatch.setattr("radar.main.answer_question", paid)
    monkeypatch.setattr("radar.main.prepare_stream", paid)
    response = client.post(path, json={"question": "总结", "client_request_id": "missing"})
    assert response.status_code == 428
    quota.reserve.assert_not_awaited()
    paid.assert_not_awaited()


@pytest.mark.parametrize("path", ["/api/v1/ask", "/api/v1/ask/stream"])
def test_twenty_first_question_rejected_before_response_stream_or_model(metered, monkeypatch, path):
    client, _, quota = metered
    client.get("/api/v1/assistant/session")
    quota.reserve.side_effect = PublicAdmissionError(
        "ASK_QUOTA_EXCEEDED",
        429,
        retry_after=123,
        quota=QuotaSnapshot(0, 5, datetime.now(UTC) + timedelta(seconds=123)),
    )
    paid = AsyncMock()
    monkeypatch.setattr("radar.main.answer_question", paid)
    monkeypatch.setattr("radar.main.prepare_stream", paid)
    response = client.post(path, json={"question": "追问", "client_request_id": "twenty-one"})
    assert response.status_code == 429 and response.headers["retry-after"] == "123"
    assert response.json()["details"]["quota"]["remaining"] == 0
    assert "text/event-stream" not in response.headers["content-type"]
    paid.assert_not_awaited()


def test_owned_request_key_and_preflight_accounting(metered, monkeypatch):
    client, identity, quota = metered
    client.get("/api/v1/assistant/session")
    paid = AsyncMock(side_effect=QaError("MODEL_UNAVAILABLE", "unavailable", 503))
    monkeypatch.setattr("radar.main.answer_question", paid)
    response = client.post("/api/v1/ask", json={"question": "总结", "client_request_id": "key"})
    assert response.status_code == 503
    assert quota.reserve.await_args.args[0] == identity.subject(client.cookies.get(COOKIE))
    assert quota.reserve.await_args.args[2] == "key"
    assert paid.await_args.args[0].client_request_id == f"pub-{quota.reserve.return_value.id.hex}"
    PublicRun.finish.assert_awaited_once_with(completed=False)


def test_unconfigured_accounting_fails_closed(metered, monkeypatch):
    client, _, _ = metered
    app.state.public_quota = None
    paid = AsyncMock()
    monkeypatch.setattr("radar.main.answer_question", paid)
    response = client.post("/api/v1/ask", json={"question": "总结", "client_request_id": "key"})
    assert response.status_code == 503
    assert response.json()["code"] == "ASSISTANT_QUOTA_UNAVAILABLE"
    paid.assert_not_awaited()
