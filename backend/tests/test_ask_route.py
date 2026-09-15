from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from radar.qa_limits import AskAdmission


def test_real_route_uses_saved_config_and_limits_admission(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import radar.main as main

    config = tmp_path / "model.json"
    config.write_text('{"api_key":"test-key","enabled":false,"max_tokens":32}')
    client.app.state.settings.model_config_path = config
    client.app.state.sessions = object()
    client.app.state.ask_admission = AskAdmission(per_client=1)
    service = AsyncMock(return_value={"answer": "ok"})
    monkeypatch.setattr(main, "answer_question", service)
    payload = {"question": "分析", "client_request_id": "route-check"}
    assert client.post("/api/v1/ask", json=payload).status_code == 200
    assert service.await_args.args[-1].llm_api_key is None
    assert service.await_args.args[-1].llm_max_tokens == 32
    limited = client.post("/api/v1/ask", json=payload)
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"
    assert service.await_count == 1
    config.write_text("broken")
    failed = client.post("/api/v1/ask", json=payload)
    assert failed.status_code == 503
    assert failed.json()["code"] == "MODEL_CONFIG_UNAVAILABLE"
    assert service.await_count == 1
