import pytest
from fastapi.testclient import TestClient

from radar.config import get_settings
from radar.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RADAR_DATA_MODE", "fixture")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
