from uuid import uuid4

from starlette.requests import Request

from radar.main import _admin_audit_target


def _request(method: str, path: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": []})


def test_audit_targets_only_known_admin_write_routes() -> None:
    source_id = uuid4()
    assert _admin_audit_target(_request("POST", "/api/v1/admin/session")) == (
        "session.login",
        "session",
    )
    assert _admin_audit_target(_request("PATCH", f"/api/v1/admin/sources/{source_id}")) == (
        "source.update",
        f"source:{source_id}",
    )
    assert _admin_audit_target(_request("POST", "/api/v1/ingest/runs")) == (
        "ingest.start",
        "ingest-runs",
    )
    assert _admin_audit_target(_request("POST", "/api/v1/admin/attacker-secret")) is None
    assert _admin_audit_target(_request("GET", "/api/v1/admin/sources")) is None
