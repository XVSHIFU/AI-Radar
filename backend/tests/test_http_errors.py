import uuid

from fastapi.testclient import TestClient

from radar.main import app


def test_unknown_api_route_uses_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/api/no-such-route")
    assert response.status_code == 404
    assert response.json()["code"] == "HTTP_ERROR"
    assert response.json()["message"] == "Not Found"
    uuid.UUID(response.json()["request_id"])
