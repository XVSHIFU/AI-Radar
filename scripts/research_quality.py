"""Offline frozen-corpus validation and human-reviewed legacy/Agent comparison.

No network, database, model calls or application configuration is loaded here.
This tool never infers semantic correctness from a citation merely existing.
"""

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "agent/research/evals/quality-v1.json"
FROZEN_SHA256 = "57cd0133455918a8bb26e367469e39fe3c2b9a3e1da3b54c5c2000c1bc6af5e6"
CATEGORIES = (
    "model_release",
    "agent_tool",
    "framework_sdk",
    "research",
    "product",
    "industry",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def verified(item):
    return (
        item["date_precision"] == "day"
        and item["event_date"] is not None
        and item["date_basis"] in ("explicit_body", "official_publication")
        and item["date_conflict"] is False
    )


def selected(events, scope):
    answer = []
    for item in events:
        if scope.get("category") and item["category"] != scope["category"]:
            continue
        if scope.get("events") and item["key"] not in scope["events"]:
            continue
        if scope.get("date_from") or scope.get("date_to"):
            if not verified(item):
                continue
            if scope.get("date_from") and item["event_date"] < scope["date_from"]:
                continue
            if scope.get("date_to") and item["event_date"] > scope["date_to"]:
                continue
        answer.append(item)
    return answer


def validate(corpus):
    body = {k: v for k, v in corpus.items() if k != "content_sha256"}
    digest = hashlib.sha256(canonical(body)).hexdigest()
    require(
        digest == corpus.get("content_sha256") == FROZEN_SHA256,
        "frozen corpus hash mismatch",
    )
    require(
        corpus["evaluation_status"] == "not_run",
        "corpus must not claim evaluation success",
    )
    require(
        corpus["human_semantic_review"] == "required",
        "human review requirement missing",
    )
    require(
        corpus["targets"]
        == {
            "task_completion": 0.9,
            "citation_location": 1.0,
            "semantic_consistency": 0.95,
        },
        "original quality targets changed",
    )
    events, cases = corpus["events"], corpus["cases"]
    require(len(events) == 12 and len(cases) == 40, "unexpected frozen corpus size")
    require(
        {c["id"] for c in cases} == {f"Q{i:02d}" for i in range(1, 41)},
        "case IDs missing",
    )
    require(
        {c["kind"] for c in cases}
        == {
            "explain",
            "evidence",
            "scope",
            "count",
            "compare",
            "missing",
            "security",
            "memory",
        },
        "required coverage missing",
    )
    seen = set()
    for item in events:
        require(
            item["id"] not in seen and str(UUID(item["id"])) == item["id"],
            "duplicate event",
        )
        seen.add(item["id"])
        require(item["category"] in CATEGORIES, "unknown category")
        if item["event_date"]:
            date.fromisoformat(item["event_date"])
        for evidence in item["evidence"]:
            require(evidence["id"] not in seen, "duplicate evidence")
            seen.add(evidence["id"])
            require(
                hashlib.sha256(evidence["quote_text"].encode()).hexdigest()
                == evidence["quote_sha256"],
                "quote hash mismatch",
            )
            require(
                evidence["source_url"].startswith(
                    "https://example.invalid/quality-v1/"
                ),
                "fixture must not point to a live source",
            )
    by_key = {item["key"]: item for item in events}
    require(len(by_key) == 12, "duplicate event key")
    for case in cases:
        expected, scope = case["required"], case["scope"]
        require(
            case["request"]["question"] == case["question"], "question/request mismatch"
        )
        mapped = {k: v for k, v in scope.items() if k != "events"}
        if "events" in scope:
            mapped["event_ids"] = [by_key[key]["id"] for key in scope["events"]]
        require(case["request"]["filters"] == mapped, "scope/request mismatch")
        rows = selected(events, scope)
        if "count" in expected:
            require(
                expected["count"] == len(rows), f"{case['id']}: count oracle mismatch"
            )
        if "counts" in expected:
            counts = Counter(item["category"] for item in rows)
            require(
                expected["counts"] == {k: counts[k] for k in CATEGORIES},
                f"{case['id']}: category oracle mismatch",
            )
        if "first" in expected:
            counts = [
                len(
                    selected(
                        events, {**scope, "date_from": p["from"], "date_to": p["to"]}
                    )
                )
                for p in case["periods"]
            ]
            first, second = counts
            percent = (second - first) / first * 100 if first else None
            require(
                (
                    expected["first"],
                    expected["second"],
                    expected["difference"],
                    expected["increase_percent"],
                )
                == (first, second, second - first, percent),
                f"{case['id']}: period oracle mismatch",
            )
        require(
            all(key in by_key for key in expected.get("events", [])),
            "unknown expected event",
        )
    keyed = {item["id"]: item for item in cases}
    before, after = (by_key[key]["facts"]["context_tokens"] for key in ("E02", "E03"))
    require(
        keyed["Q02"]["required"]["difference_tokens"] == after - before,
        "context difference",
    )
    require(
        keyed["Q02"]["required"]["increase_percent"] == (after - before) / before * 100,
        "context percentage",
    )
    facts = by_key["E06"]["facts"]
    require(
        keyed["Q31"]["required"]["task_completion_percent"]
        == facts["completed"] / facts["tasks"] * 100,
        "experiment oracle",
    )
    require(
        set(keyed["Q22"]["required"]["excluded"])
        == {e["key"] for e in events if not verified(e)},
        "date exclusions",
    )
    require(
        {e["name"] for e in corpus["entities"] if "Orion" in e["aliases"]}
        == set(keyed["Q15"]["required"]["candidates"]),
        "ambiguity fixture",
    )
    return {
        "status": "corpus_valid",
        "cases": len(cases),
        "events": len(events),
        "sha256": digest,
        "evaluation_status": "not_run",
    }


def template(corpus):
    validate(corpus)
    return {
        "corpus_sha256": corpus["content_sha256"],
        "variants": {
            name: {
                "configuration": None,
                "cases": [
                    {"id": case["id"], "execution": None, "review": None}
                    for case in corpus["cases"]
                ],
            }
            for name in ("legacy", "agent")
        },
    }


def variant_score(corpus, result):
    expected = {c["id"]: c for c in corpus["cases"]}
    rows = result.get("cases", [])
    ids = [row.get("id") for row in rows]
    require(
        len(ids) == len(set(ids)) and set(ids) == set(expected),
        "case results missing/duplicated",
    )
    incomplete, tasks, claims, located = [], [], [], []
    groups = {}
    mandatory_failures = []
    timings = {"first_token_ms": [], "duration_ms": []}
    usage = {
        "model_calls": 0,
        "input_tokens_known": 0,
        "output_tokens_known": 0,
        "input_tokens_unknown_cases": 0,
        "output_tokens_unknown_cases": 0,
    }
    for row in rows:
        key = row["id"]
        execution, review = row.get("execution"), row.get("review")
        if not isinstance(execution, dict) or not isinstance(review, dict):
            incomplete.append(key)
            continue
        require(
            execution.get("status") in {"completed", "failed", "cancelled", "rejected"},
            f"{key}: invalid execution status",
        )
        require(
            isinstance(execution.get("answer"), str), f"{key}: answer/draft missing"
        )
        require(
            isinstance(review.get("reviewer"), str) and review["reviewer"].strip(),
            f"{key}: reviewer required",
        )
        require(
            review.get("all_factual_claims_reviewed") is True,
            f"{key}: incomplete claim review",
        )
        require(
            type(review.get("task_completed")) is bool, f"{key}: task judgment required"
        )
        require(
            isinstance(review.get("notes"), str) and review["notes"].strip(),
            f"{key}: review rationale required",
        )
        reviewed_claims = review.get("claims")
        checks = review.get("citation_checks")
        citations = execution.get("citations")
        require(
            all(isinstance(v, list) for v in (reviewed_claims, checks, citations)),
            f"{key}: explicit claim/citation lists required",
        )
        indices = [c.get("index") for c in citations]
        require(
            all(type(i) is int and 1 <= i <= 60 for i in indices)
            and len(indices) == len(set(indices)),
            f"{key}: invalid published citations",
        )
        require(
            len(checks) == len(indices)
            and {c.get("index") for c in checks} == set(indices),
            f"{key}: each citation needs a location check",
        )
        for claim in reviewed_claims:
            require(
                type(claim.get("supported")) is bool
                and bool(claim.get("text"))
                and bool(claim.get("evidence")),
                f"{key}: incomplete semantic judgment",
            )
            claims.append(claim["supported"])
        for check in checks:
            require(
                type(check.get("located")) is bool and bool(check.get("locator")),
                f"{key}: location check needs an inspectable locator",
            )
            located.append(check["located"])
        passed = review["task_completed"]
        case = expected[key]
        outcome = case["required"].get("outcome")
        acceptable = {"completed"}
        if outcome == "cancelled":
            acceptable = {"cancelled"}
        elif outcome == "reject_unregistered_citation":
            acceptable = {"failed", "rejected"}
        elif outcome in {
            "clarify_attachment_conflict",
            "clarify_entity",
            "request_explicit_scope_change",
        }:
            acceptable.add("rejected")
        if execution["status"] not in acceptable:
            passed = False
        # A claimed success cannot override a known protocol/grounding failure.
        if case["required"].get("citations_required") and (
            not citations or not reviewed_claims
        ):
            passed = False
        if execution["status"] != "completed" and citations:
            passed = False
        if case["required"].get("formal_citations") is False and citations:
            passed = False
        if case.get("setup", {}).get("check"):
            outcomes = execution.get("client_checks", {})
            if any(outcomes.get(name) is not True for name in case["setup"]["check"]):
                passed = False
        metrics = execution.get("metrics")
        require(isinstance(metrics, dict), f"{key}: metrics missing")
        calls = metrics.get("model_calls")
        require(
            type(calls) is int and calls >= 0, f"{key}: actual model call count missing"
        )
        usage["model_calls"] += calls
        for field in ("input_tokens", "output_tokens"):
            value = metrics.get(field)
            require(
                field in metrics
                and (value is None or type(value) is int and value >= 0),
                f"{key}: invalid token usage",
            )
            usage[field + ("_unknown_cases" if value is None else "_known")] += (
                1 if value is None else value
            )
        for field in ("first_token_ms", "duration_ms"):
            value = metrics.get(field)
            require(
                field in metrics
                and (
                    value is None
                    or type(value) in (int, float)
                    and math.isfinite(value)
                    and value >= 0
                ),
                f"{key}: invalid timing",
            )
            if value is not None:
                timings[field].append(value)
        if not passed and (
            case["kind"] in {"security", "memory"} or key in {"Q13", "Q14", "Q27"}
        ):
            mandatory_failures.append(key)
        tasks.append(passed)
        groups.setdefault(case["verification"], []).append(passed)
    rates = {
        "task_completion": sum(tasks) / 40,
        "citation_location": sum(located) / len(located) if located else None,
        "semantic_consistency": sum(claims) / len(claims) if claims else None,
    }
    complete = not incomplete and all(value is not None for value in rates.values())
    passed = (
        complete
        and not mandatory_failures
        and all(rates[k] >= v for k, v in corpus["targets"].items())
    )
    return {
        "status": "passed" if passed else "failed" if complete else "incomplete",
        "missing_reviews": incomplete,
        "mandatory_failures": mandatory_failures,
        "timings": {
            key: {
                "observed": len(values),
                "unknown": len(tasks) - len(values),
                "p50": sorted(values)[math.ceil(len(values) * 0.5) - 1]
                if values
                else None,
                "p95": sorted(values)[math.ceil(len(values) * 0.95) - 1]
                if values
                else None,
            }
            for key, values in timings.items()
        },
        "rates": rates,
        "reviewed_claims": len(claims),
        "reviewed_citations": len(located),
        "usage": usage,
        "groups": {
            k: {"passed": sum(v), "reviewed": len(v)} for k, v in groups.items()
        },
    }


def score(corpus, results):
    validate(corpus)
    require(
        results.get("corpus_sha256") == corpus["content_sha256"], "wrong result corpus"
    )
    variants = results.get("variants", {})
    require(
        set(variants) == {"legacy", "agent"}, "both comparison variants are required"
    )
    output = {key: variant_score(corpus, value) for key, value in variants.items()}
    configs = [variants[key].get("configuration") for key in ("legacy", "agent")]
    comparable = all(
        isinstance(c, dict)
        and all(
            c.get(k) is not None
            for k in (
                "provider",
                "model",
                "max_output_tokens",
                "code_revision",
            )
        )
        for c in configs
    )
    if comparable:
        comparable = all(
            configs[0][k] == configs[1][k]
            for k in ("provider", "model", "max_output_tokens")
        )
    complete = comparable and all(v["status"] != "incomplete" for v in output.values())
    improved = (
        complete
        and (
            output["agent"]["rates"]["task_completion"]
            > output["legacy"]["rates"]["task_completion"]
        )
        and all(
            output["agent"]["rates"][k] >= output["legacy"]["rates"][k]
            for k in ("citation_location", "semantic_consistency")
        )
    )
    eligible = output["agent"]["status"] == "passed" and improved
    return {
        "status": "reviewed" if complete else "incomplete",
        "comparable": comparable,
        "variants": output,
        "quality_release_eligible": eligible,
        "note": "Quality gate only; deployment/security/restore gates remain independent.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "template", "score"))
    parser.add_argument("--results", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    if args.command == "validate":
        result = validate(corpus)
    elif args.command == "template":
        result = template(corpus)
    else:
        require(args.results is not None, "--results is required")
        result = score(corpus, json.loads(args.results.read_text(encoding="utf-8")))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        # Never overwrite a human's review record or a previous result.
        with args.output.open("x", encoding="utf-8") as target:
            target.write(rendered)
    else:
        print(rendered)
    if args.command == "score":
        return 0 if result["quality_release_eligible"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
