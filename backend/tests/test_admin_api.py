import json
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar.config import Settings, get_settings
from radar.main import app
from radar.model_config import ModelConfigStore, ModelConfigUnavailable, effective_model_settings


def test_admin_session_cookie_csrf_and_logout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_DATA_MODE", "fixture")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/admin/session").json() == {"authenticated": False}
            bad = client.post("/api/v1/admin/session", json={"token": "wrong"})
            assert bad.status_code == 401
            response = client.post("/api/v1/admin/session", json={"token": "test-admin-token"})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert "HttpOnly" in response.headers["set-cookie"]
            assert "SameSite=strict" in response.headers["set-cookie"]
            csrf = response.json()["csrf_token"]
            assert client.delete("/api/v1/admin/session").status_code == 403
            assert (
                client.delete("/api/v1/admin/session", headers={"X-CSRF-Token": csrf}).status_code
                == 204
            )
            assert client.get("/api/v1/admin/session").json() == {"authenticated": False}
    finally:
        get_settings.cache_clear()


def test_model_config_is_atomic_effective_and_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "model.json"
    settings = Settings(
        radar_data_mode="fixture",
        llm_api_key="env-key",
        model_config_path=path,
    )
    store = ModelConfigStore(settings)
    initial = store.read()
    assert initial.api_key == "env-key"
    updated = store.update(api_key="stored-key", enabled=True, max_tokens=31)
    assert updated.api_key == "stored-key"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    effective = effective_model_settings(settings)
    assert effective.llm_api_key == "stored-key"
    assert effective.llm_model == "deepseek-flash"
    assert effective.llm_max_tokens == 31
    payload = json.loads(path.read_text())
    assert payload["api_key"] == "stored-key"
    path.write_text("not-json")
    with pytest.raises(ModelConfigUnavailable):
        store.read()
