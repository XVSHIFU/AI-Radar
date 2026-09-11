"""Independent frozen synthetic structure evaluation; never counts pending cases as passes."""

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "contracts/regression/cases-v1.json"
    )
    args = parser.parse_args()
    corpus_path = ROOT / "contracts/regression/synthetic-structure-v1.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    manifest = json.loads(args.cases.read_text(encoding="utf-8"))
    keys = corpus["event_keys"]
    case_ids = [case["case_id"] for case in manifest["cases"]]
    if len(case_ids) != len(set(case_ids)) or manifest["dataset"] != corpus["dataset"]:
        raise ValueError(
            "Evaluation configuration error: duplicate cases or dataset mismatch"
        )
    required_ids = {
        f"{prefix}{n:02d}"
        for prefix, count in (("T", 10), ("C", 6), ("E", 8), ("N", 6), ("R", 6))
        for n in range(1, count + 1)
    }
    if set(case_ids) != required_ids:
        raise ValueError(
            "Evaluation configuration error: P0 case inventory is incomplete"
        )
    for case in manifest["cases"]:
        if case["layer"] == "pending":
            if not case.get("reason"):
                raise ValueError("Pending case must have an explicit reason")
            continue
        for field in (
            "filters",
            "expected_event_keys",
            "forbidden_event_keys",
            "checks",
        ):
            if field not in case:
                raise ValueError(
                    f"Evaluation configuration error: {case['case_id']} lacks {field}"
                )
        referenced = case["expected_event_keys"] + case["forbidden_event_keys"]
        for variant in case.get("variants", []):
            referenced += variant["expected_event_keys"]
        if not set(referenced) <= keys.keys():
            raise ValueError("Evaluation configuration error: unknown expected key")

    os.environ["RADAR_DATA_MODE"] = "fixture"
    from fastapi.testclient import TestClient
    from radar.config import get_settings
    from radar.fixture_repository import FixtureRepository
    from radar.main import app, get_repository

    get_settings.cache_clear()
    repository = FixtureRepository(
        corpus_path, "synthetic-structure-cursor-only", items=corpus["items"]
    )
    repository.now = datetime.fromisoformat(
        manifest["fixed_clock"].replace("Z", "+00:00")
    )
    app.dependency_overrides[get_repository] = lambda: repository
    results = []

    def query_scope(
        client: TestClient, filters: dict, expected_keys: list[str], page_size: int
    ) -> list[str]:
        ids, totals, cursor = [], [], None
        for _ in range(100):
            params = {**filters, "limit": page_size}
            if cursor:
                params["cursor"] = cursor
            response = client.get("/api/v1/events", params=params)
            assert response.status_code == 200, response.text
            page = response.json()
            assert page["total_relation"] == "eq"
            totals.append(page["total"])
            ids.extend(row["id"] for row in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        expected = {keys[key] for key in expected_keys}
        assert cursor is None, "Pagination did not terminate"
        assert set(ids) == expected, {"actual": ids, "expected": sorted(expected)}
        assert len(ids) == len(set(ids)) == len(expected), "Duplicate or missing event"
        assert set(totals) == {len(expected)}, "Exact total changed across pages"
        return ids

    try:
        with TestClient(app) as client:
            for case in manifest["cases"]:
                if case["layer"] == "pending":
                    results.append(
                        {
                            "case_id": case["case_id"],
                            "status": "not_implemented",
                            "reason": case["reason"],
                        }
                    )
                    continue
                try:
                    ids = query_scope(
                        client,
                        case["filters"],
                        case["expected_event_keys"],
                        case.get("page_size", 2),
                    )
                    assert not (
                        set(ids) & {keys[key] for key in case["forbidden_event_keys"]}
                    )
                    for variant in case.get("variants", []):
                        query_scope(
                            client,
                            variant["filters"],
                            variant["expected_event_keys"],
                            1,
                        )
                    if "invalid_filters" in case:
                        response = client.get(
                            "/api/v1/events", params=case["invalid_filters"]
                        )
                        assert response.status_code == case["expected_error_status"]
                        assert {
                            "code",
                            "message",
                            "retryable",
                            "request_id",
                        } <= response.json().keys()
                    if case.get("expected_answer_status") == "no_answer":
                        response = client.post(
                            "/api/v1/ask",
                            json={
                                "question": case["question"],
                                "filters": case["filters"],
                                "timezone": manifest["timezone"],
                                "client_request_id": "synthetic-" + case["case_id"],
                            },
                        )
                        assert response.status_code == 200, response.text
                        answer = response.json()
                        assert answer["answer_status"] == "no_answer"
                        assert (
                            answer["execution_status"] == "completed"
                            and answer["citations"] == []
                        )
                    if "no_invented_evidence" in case["checks"]:
                        for event_id in ids:
                            detail = client.get(f"/api/v1/events/{event_id}").json()
                            evidence = client.get(
                                f"/api/v1/events/{event_id}/evidence"
                            ).json()
                            assert detail["evidence_count"] == 0
                            assert evidence["items"] == [] and detail["articles"] == []
                    results.append(
                        {
                            "case_id": case["case_id"],
                            "status": "structural_pass",
                            "actual_event_ids": ids,
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "case_id": case["case_id"],
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
    finally:
        app.dependency_overrides.clear()

    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "dataset": corpus["dataset"],
        "layer": "synthetic_explicit_filter_asgi",
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        "fixed_clock": manifest["fixed_clock"],
        "timezone": manifest["timezone"],
        "enabled": len(results),
        "structural_pass": sum(x["status"] == "structural_pass" for x in results),
        "failed": sum(x["status"] == "failed" for x in results),
        "not_implemented": sum(x["status"] == "not_implemented" for x in results),
        "historical_gold_verified": False,
        "natural_language_verified": False,
        "postgres_verified": False,
        "live_model_verified": False,
        "phase1_phase2_not_enabled": 12,
        "checks": results,
    }
    (ROOT / "docs/structure-regression-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("enabled", "structural_pass", "failed", "not_implemented")
            }
        )
    )
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
