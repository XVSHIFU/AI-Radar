"""Negative HTTP checks against a reserved loopback port that is deliberately not listening."""
import json
import os
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main() -> int:
    results = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        os.environ["RADAR_DATA_MODE"] = "postgres"
        os.environ["DATABASE_URL"] = f"postgresql+asyncpg://synthetic@127.0.0.1:{port}/synthetic"
        os.environ["ADMIN_TOKEN"] = "synthetic-local-test"
        from fastapi.testclient import TestClient
        from radar.config import get_settings
        from radar.main import app

        get_settings.cache_clear()
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                for method, path in (("GET", "/api/v1/events"), ("GET", "/api/v1/ingest/runs"), ("POST", "/api/v1/ingest/runs")):
                    options = {"headers": {"Authorization": "Bearer synthetic-local-test", "Idempotency-Key": "synthetic-unavailable-db"}}
                    if method == "POST":
                        options["json"] = {"source_ids": ["10000000-0000-4000-8000-000000000001"]}
                    response = client.request(method, path, **options)
                    try:
                        body = response.json()
                    except ValueError:
                        body = {"message": response.text[:200]}
                    passed = (
                        response.status_code == 503
                        and body.get("code") in {"RETRIEVAL_FAILED", "DATABASE_UNAVAILABLE"}
                        and body.get("retryable") is True
                        and bool(body.get("request_id"))
                    )
                    results.append({"method": method, "path": path, "status": response.status_code, "body": body, "passed": passed})
        finally:
            get_settings.cache_clear()
    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "layer": "real_loopback_connection_refused_no_postgresql_server",
        "postgres_integration_executed": False,
        "passed": sum(item["passed"] for item in results),
        "total": len(results), "checks": results,
    }
    (ROOT / "docs/database-unavailable-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "total": report["total"]}))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
