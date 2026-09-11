"""Independent HTTP checks of frozen deterministic plans, without a model or PostgreSQL."""
import hashlib
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main() -> int:
    manifest_path = ROOT / "contracts/regression/query-plan-cases-v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = [case["id"] for case in manifest["cases"]]
    if len(ids) != 30 or len(set(ids)) != 30:
        raise ValueError("Frozen plan case inventory must contain 30 distinct IDs")
    for case in manifest["cases"]:
        if not any(key in case for key in ("expected_filters", "requires_clarification", "expected_status")):
            raise ValueError("Case has no expected assertion")
    os.environ["RADAR_DATA_MODE"] = "fixture"
    os.environ["LLM_API_KEY"] = ""
    from fastapi.testclient import TestClient
    from radar.config import get_settings
    from radar.main import app, get_clock

    get_settings.cache_clear()
    fixed = datetime.fromisoformat(manifest["fixed_clock"])
    app.dependency_overrides[get_clock] = lambda: fixed
    results = []
    try:
        with TestClient(app) as client:
            for case in manifest["cases"]:
                fixed = datetime.fromisoformat(case.get("clock", manifest["fixed_clock"]))
                payload = {
                    "question": case["question"], "filters": case.get("filters", {}),
                    "timezone": case.get("timezone", manifest["timezone"]),
                    "client_request_id": "synthetic-plan-" + case["id"],
                }
                record = {"id": case["id"], "passed": False}
                try:
                    response = client.post("/api/v1/query-plan", json=payload)
                    expected_status = case.get("expected_status", 200)
                    assert response.status_code == expected_status, response.text
                    body = response.json()
                    if expected_status == 200:
                        assert body["timezone"] == payload["timezone"]
                        assert body["data_mode"] == "fixture"
                        assert body["request_id"]
                        assert body["requires_clarification"] == case["requires_clarification"]
                        for field, expected in case.get("expected_filters", {}).items():
                            actual = body["filters"].get(field)
                            assert (sorted(actual) == sorted(expected) if isinstance(expected, list) else actual == expected), {
                                "field": field, "actual": actual, "expected": expected,
                            }
                        if 'expected_free_text' in case:
                            assert body['free_text'] == case['expected_free_text']
                        if case.get("warnings_required"):
                            assert body["warnings"], "UI conflict must be disclosed"
                        end = body["filters"].get("date_to")
                        if end:
                            assert body["date_until_exclusive"] == (date.fromisoformat(end) + timedelta(days=1)).isoformat()
                        if body["requires_clarification"]:
                            ask = client.post("/api/v1/ask", json=payload)
                            assert ask.status_code == 422, ask.text
                            assert ask.json()["code"] == "CLARIFICATION_REQUIRED"
                            assert ask.json()["details"]["query_plan_public"]["requires_clarification"]
                    else:
                        assert body["code"] == "VALIDATION_ERROR"
                    record.update(passed=True, response=body)
                except (AssertionError, KeyError, TypeError, ValueError) as exc:
                    record["error"] = str(exc)
                results.append(record)
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "layer": "synthetic_deterministic_plan_http",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "postgres_executed": False, "live_model_executed": False, "historical_gold": False,
        "passed": sum(item["passed"] for item in results), "total": len(results), "checks": results,
    }
    (ROOT / "docs/query-plan-regression-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps({"passed": report["passed"], "total": report["total"]}))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
