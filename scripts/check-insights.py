"""Independent HTTP checks for complete-range event aggregation."""
import argparse
import json
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8002")
args = parser.parse_args()
fixture = json.loads((root / "contracts/prototype-events.json").read_text(encoding="utf-8-sig"))["items"]
checks = []

def request(params):
    try:
        with urlopen(args.base_url + "/api/v1/insights/summary?" + urlencode(params), timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)

def check(name, filters, expected_status=200):
    try:
        status, actual = request(filters)
        assert status == expected_status, (status, actual)
        if status == 200:
            lo, hi = date.fromisoformat(filters["date_from"]), date.fromisoformat(filters["date_to"])
            rows = [r for r in fixture if r.get("event_date") and
                    filters["date_from"] <= r["event_date"] <= filters["date_to"] and
                    (not filters.get("category") or r["category"] == filters["category"]) and
                    (not filters.get("min_importance") or r["importance"] >= filters["min_importance"]) and
                    (not filters.get("q") or filters["q"].casefold() in
                     (r["title_zh"] + " " + r["summary_zh"] + " " + " ".join(r["entities"])).casefold())]
            expected_daily = {str(lo + timedelta(days=i)): 0 for i in range((hi-lo).days+1)}
            expected_cats = dict.fromkeys(["model_release","agent_tool","framework_sdk","research","product","industry"],0)
            for row in rows:
                expected_daily[row["event_date"]] += 1
                expected_cats[row["category"]] += 1
            assert actual["total_events"] == len(rows), actual
            assert actual["total_relation"] == "eq" and actual["data_mode"] == "fixture"
            assert actual["date_from"] == str(lo) and actual["date_to"] == str(hi)
            assert actual["timezone"] == "Asia/Shanghai"
            assert {d["date"]:d["count"] for d in actual["daily"]} == expected_daily
            assert len(actual["daily"]) == len(expected_daily)
            assert {c["category"]:c["count"] for c in actual["categories"]} == expected_cats
            assert len(actual["categories"]) == 6
            assert sum(d["count"] for d in actual["daily"]) == sum(c["count"] for c in actual["categories"]) == actual["total_events"]
            assert actual["as_of"] and actual["data_revision"] and actual["request_id"]
        else:
            assert actual.get("code") and actual.get("message"), actual
        checks.append({"check":name,"layer":"fixture_api_http","passed":True,"status":status,
                       "total_events":actual.get("total_events")})
    except Exception as error:
        checks.append({"check":name,"layer":"fixture_api_http","passed":False,"error":str(error)})

check("full_fixture_exceeds_first_page", {"date_from":"2026-09-01","date_to":"2026-09-30"})
check("inclusive_one_day", {"date_from":"2026-09-12","date_to":"2026-09-12"})
check("category_range_exact", {"date_from":"2026-09-08","date_to":"2026-09-10","category":"agent_tool"})
check("keyword_combined_category", {"date_from":"2026-09-01","date_to":"2026-09-30","q":"DeepSeek","category":"model_release"})
check("zero_days_filled", {"date_from":"2099-01-01","date_to":"2099-01-07"})
check("leap_day_inclusive", {"date_from":"2024-02-28","date_to":"2024-03-01"})
check("maximum_366_days", {"date_from":"2025-09-14","date_to":"2026-09-14"})
check("importance_filtered", {"date_from":"2026-09-08","date_to":"2026-09-12","min_importance":4})
check("reject_reverse", {"date_from":"2026-09-14","date_to":"2026-09-13"},422)
check("reject_367_days", {"date_from":"2025-09-13","date_to":"2026-09-14"},422)
check("require_dates", {},422)
check("reject_unknown_category", {"date_from":"2026-09-01","date_to":"2026-09-12","category":"fiction"},422)
report={"observed_at":datetime.now(timezone.utc).isoformat(),"base_url":args.base_url,
        "passed":sum(c["passed"] for c in checks),"total":len(checks),"checks":checks}
(root/"docs/insights-http-results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
raise SystemExit(0 if all(c["passed"] for c in checks) else 1)
