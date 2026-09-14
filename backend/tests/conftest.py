import pytest
from fastapi.testclient import TestClient

from radar.config import get_settings
from radar.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RADAR_DATA_MODE", "fixture")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("ADMIN_TOKEN", "")
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
