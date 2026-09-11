"""HTTP contract smoke checks against explicit synthetic mode; no paid calls."""
import argparse
import datetime
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_DATE_IDS = {
    "00000000-0000-4000-8000-000000000013",
    "00000000-0000-4000-8000-000000000019",
    "00000000-0000-4000-8000-000000000025",
}


def request(base, path, query=None, body=None):
    if query:
        path += "?" + urllib.parse.urlencode(query, doseq=True)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    results = []

    def check(name, condition, observed):
        results.append({"check": name, "passed": bool(condition), "observed": observed})

    status, first = request(args.base_url, "/api/v1/events", {"limit": 3})
    if status != 200 or first.get("data_mode") != "fixture":
        raise SystemExit("This runner requires a running API with RADAR_DATA_MODE=fixture.")
    ids, cursor, totals = [], None, []
    for _ in range(20):
        query = {"limit": 3}
        if cursor:
            query["cursor"] = cursor
        status, page = request(args.base_url, "/api/v1/events", query)
        if status != 200:
            raise AssertionError(page)
        ids.extend(item["id"] for item in page["items"])
        totals.append(page["total"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    expected_all = {item["id"] for item in json.loads((ROOT / "contracts/prototype-events.json").read_text(encoding="utf-8"))["items"]}
    check("all_pages_exact_set_and_total", set(ids) == expected_all and len(ids) == len(set(ids)) == 32 and set(totals) == {32} and not cursor, {"count": len(ids), "unique": len(set(ids)), "totals": sorted(set(totals))})
    status, page = request(args.base_url, "/api/v1/events", {"category": "agent_tool", "date_from": "2026-09-08", "date_to": "2026-09-10"})
    check("inclusive_dates_exact_ids", status == 200 and page["total"] == 3 and {item["id"] for item in page["items"]} == EXPECTED_DATE_IDS, page.get("total"))
    for alias in ("DeepSeek", "深度求索", "ＤｅｅｐＳｅｅｋ"):
        status, page = request(args.base_url, "/api/v1/events", {"q": alias})
        check("entity_alias_" + alias, status == 200 and page["total"] == 6, page.get("total"))
    status, page = request(args.base_url, "/api/v1/events", {"q": "MCP", "entity_ids": "10000000-0000-4000-8000-000000000002"})
    check("keyword_and_entity_intersection", status == 200 and page["total"] == 5, page.get("total"))
    for name, query in (("category", {"category": "invalid"}), ("date_order", {"date_from": "2026-09-12", "date_to": "2026-09-08"}), ("limit", {"limit": 101})):
        status, body = request(args.base_url, "/api/v1/events", query)
        check("invalid_" + name, status == 422 and all(key in body for key in ("code", "message", "retryable", "request_id")), body.get("code"))
    for suffix in ("", "/evidence"):
        status, body = request(args.base_url, "/api/v1/events/ffffffff-ffff-4fff-8fff-ffffffffffff" + suffix)
        check("unknown_event" + suffix, status == 404, status)
    status, detail = request(args.base_url, "/api/v1/events/00000000-0000-4000-8000-000000000002")
    paragraphs = [article.get("paragraphs", {}) for article in detail.get("articles", [])]
    evidence = detail.get("evidence", [])
    check("evidence_locates_in_version_paragraph", status == 200 and bool(evidence) and all(any(e["paragraph_id"] in p and e["quote_text"] in p[e["paragraph_id"]] for p in paragraphs) for e in evidence), len(evidence))
    status, body = request(args.base_url, "/api/v1/ask", body={"question": "这些日期有哪些智能体工具进展？", "filters": {"category": "agent_tool", "date_from": "2026-09-08", "date_to": "2026-09-10"}, "client_request_id": "50000000-0000-4000-8000-000000000001"})
    check("unconfigured_model_not_false_no_answer", (status == 503 and body.get("code") == "MODEL_UNAVAILABLE") or (status == 200 and body.get("answer_status") == "clarification_required"), {"status": status, "code": body.get("code"), "answer_status": body.get("answer_status")})
    status, body = request(args.base_url, "/api/v1/ingest/runs")
    check("management_requires_configuration_or_auth", status in (401, 503) and bool(body.get("code")), {"status": status, "code": body.get("code")})
    report = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "layer": "synthetic_real_http", "passed": sum(item["passed"] for item in results), "total": len(results), "checks": results}
    (ROOT / "docs/api-smoke-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "total")}))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
