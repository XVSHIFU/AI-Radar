"""Prepare a reviewable, non-operational subset of the external reference pack.

No source is fetched and no model is called. The optional --apply-seeds action uses
the existing admin source API, which creates sources disabled.
"""

from __future__ import annotations

import argparse
import ipaddress
import csv
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT.parent / "AI-Radar-参考" / "data"
OUTPUT = ROOT / "data" / "content-reference"
OUTPUT_FILES = (
    "categories.csv", "workflow_status.csv", "action_suggestions.csv",
    "fetch_policies_advisory.csv", "monitors_advisory.csv",
    "entity_candidates.csv", "entity_quarantine.csv", "disabled_feed_seeds.json",
)
QUARANTINED = {
    "JAX", "Claude", "ERNIE", "GLM", "Gemini", "Gemma", "Hunyuan",
    "Llama", "BAAI", "Huawei Ascend", "MiniMax", "Perplexity", "Runway", "xAI",
}
TYPE_MAP = {
    "framework": "technology", "protocol": "technology",
    "model_family": "model", "model": "model",
    "organization": "organization",
}
CATEGORIES = {
    "model_release", "agent_tool", "framework_sdk", "research", "product", "industry"
}
ACTION_CATEGORY = {
    "model_release": "model_release", "product_launch": "product",
    "feature_release": "product", "api_release": "product",
    "general_availability": None, "open_source_release": None,
    "price_increase": "industry", "price_decrease": "industry",
    "pricing_change": "industry", "free_tier_change": "industry",
    "funding": "industry", "acquisition": "industry", "merger": "industry",
    "partnership": "industry", "investment": "industry", "personnel": "industry",
    "paper_release": "research", "benchmark_result": "research",
    "dataset_release": "research", "regulation": "industry", "milestone": "industry",
}


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader), [row for row in reader if row]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(reference: Path = REFERENCE, output: Path = OUTPUT) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    inputs = [
        "category_taxonomy.csv", "action_taxonomy.csv", "source_fetch_policies.csv",
        "first_party_monitors.csv", "entities_seed.csv", "sources.csv",
    ]
    provenance = {name: source_hash(reference / name) for name in inputs}

    fields, raw = read_csv(reference / "category_taxonomy.csv")
    if fields != ["category_code", "category_zh", "aliases", "source_notes"]:
        raise ValueError("category taxonomy header changed")
    category_rows = []
    review_status = None
    for row in raw:
        if row[0] == "needs_review":
            if len(row) != 5:
                raise ValueError("documented needs_review repair no longer applies")
            review_status = dict(zip(fields, [*row[:3], ",".join(row[3:])]))
            continue
        if len(row) != 4 or row[0] not in CATEGORIES:
            raise ValueError(f"unexpected category row: {row!r}")
        category_rows.append(dict(zip(fields, row)))
    if len(category_rows) != 6:
        raise ValueError("expected six public categories")
    write_csv(output / "categories.csv", fields, category_rows)
    if review_status is None:
        raise ValueError("needs_review status missing")
    write_csv(output / "workflow_status.csv", fields, [review_status])

    fields, raw = read_csv(reference / "action_taxonomy.csv")
    if len(raw) != 21 or set(row[1] for row in raw) != set(ACTION_CATEGORY):
        raise ValueError("action taxonomy changed; review mapping")
    actions = []
    for row in raw:
        if len(row) != len(fields):
            raise ValueError("action row width changed")
        item = dict(zip(fields, row))
        item["suggested_category"] = ACTION_CATEGORY[item["action_code"]] or ""
        item["requires_context"] = "true"  # No action word alone proves an event.
        actions.append(item)
    write_csv(output / "action_suggestions.csv", fields + ["suggested_category", "requires_context"], actions)

    fields, raw = read_csv(reference / "source_fetch_policies.csv")
    if len(raw) != 8 or len(fields) != 11:
        raise ValueError("fetch policy shape changed")
    policies = []
    for index, row in enumerate(raw, start=1):
        label = ""
        if index == 1:
            if len(row) != 13:
                raise ValueError("source range repair no longer applies")
            row = [";".join(row[:3]), *row[3:]]
        elif 2 <= index <= 5:
            if len(row) != 12:
                raise ValueError("source label repair no longer applies")
            label = row[1]
            row = [row[0], *row[2:]]
        if len(row) != len(fields):
            raise ValueError(f"fetch policy row {index} still malformed")
        item = dict(zip(fields, row))
        item["source_label"] = label
        item["operational_status"] = "advisory_only"
        policies.append(item)
    write_csv(output / "fetch_policies_advisory.csv", fields + ["source_label", "operational_status"], policies)

    fields, raw = read_csv(reference / "first_party_monitors.csv")
    if len(raw) != 10 or len(fields) != 9:
        raise ValueError("monitor shape changed")
    monitors = []
    for index, row in enumerate(raw, start=1):
        if index in (1, 8):
            if len(row) != 10:
                raise ValueError("documented monitor notes repair no longer applies")
            row = [*row[:8], ",".join(row[8:])]
        if len(row) != 9:
            raise ValueError(f"monitor row {index} still malformed")
        item = dict(zip(fields, row))
        item["adoption_status"] = "requires_page_review"
        monitors.append(item)
    write_csv(output / "monitors_advisory.csv", fields + ["adoption_status"], monitors)

    fields, raw = read_csv(reference / "entities_seed.csv")
    if len(raw) != 67:
        raise ValueError("entity pack changed; repeat identity review")
    candidates, quarantine = [], []
    for row in raw:
        if len(row) != len(fields):
            raise ValueError("entity row width changed")
        item = dict(zip(fields, row))
        name = item["canonical_name"]
        if name in QUARANTINED:
            item["quarantine_reason"] = "documented_wrong_wikidata_identity_and_derived_aliases"
            quarantine.append(item)
            continue
        item["contract_entity_type"] = TYPE_MAP.get(item["entity_type"], "")
        item["identity_status"] = "needs_review" if (
            item["ambiguity"].lower() != "false" or not item["contract_entity_type"]
            or name in {"LangChain", "LlamaIndex", "Weaviate"}
        ) else "candidate_unverified"
        # Keep names and QIDs as evidence, never as automatically approved aliases.
        item["approved_aliases"] = ""
        item["wikidata_verified_this_review"] = "false"
        candidates.append(item)
    if {row["canonical_name"] for row in quarantine} != QUARANTINED:
        raise ValueError("quarantine no longer matches the reviewed 14 identities")
    write_csv(output / "entity_candidates.csv", fields + [
        "contract_entity_type", "identity_status", "approved_aliases", "wikidata_verified_this_review"
    ], candidates)
    write_csv(output / "entity_quarantine.csv", fields + ["quarantine_reason"], quarantine)

    seeds = [
        {"source_ref": "S008", "name": "Hugging Face", "feed_url": "https://huggingface.co/blog/feed.xml",
         "channel_type": "rss", "enabled": False, "health": "unverified",
         "review_basis": "reference-review-20260919 XML snapshot; existing built-in candidate"},
        {"source_ref": "new-official-groq", "name": "Groq Official Changelog",
         "feed_url": "https://github.com/groq/groq-changelog/commits/main.atom",
         "channel_type": "rss", "enabled": False, "health": "unverified",
         "review_basis": "reference-review-20260919 XML snapshot; commit feed needs article validation"},
    ]
    _, source_rows = read_csv(reference / "sources.csv")
    if len(source_rows) != 64:
        raise ValueError("source candidate pack changed")
    (output / "disabled_feed_seeds.json").write_bytes(
        (json.dumps(seeds, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    manifest = {
        "source": "AI-Radar-参考/data (read-only)", "review": "docs/reference-review-20260919.md",
        "input_sha256": provenance, "row_counts": {"categories": 6, "workflow_status": 1, "actions": len(actions),
        "fetch_policies_advisory": len(policies), "monitors_advisory": len(monitors),
        "entity_candidates": len(candidates), "entity_quarantine": len(quarantine),
        "disabled_feed_seeds": len(seeds)},
        "repaired_row_widths": {"category_taxonomy.csv": 1,
                                "source_fetch_policies.csv": 5, "first_party_monitors.csv": 2},
        "publication_status": "reference_only",
        "output_sha256": {name: source_hash(output / name) for name in OUTPUT_FILES},
    }
    (output / "manifest.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return manifest


def checked_prepared(output: Path) -> dict[str, object]:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    hashes = manifest.get("output_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(OUTPUT_FILES):
        raise ValueError("prepared dataset manifest is incomplete")
    for name in OUTPUT_FILES:
        if source_hash(output / name) != hashes[name]:
            raise ValueError(f"prepared dataset hash mismatch: {name}")
    if manifest.get("row_counts", {}).get("disabled_feed_seeds") != 2:
        raise ValueError("unexpected number of prepared feed seeds")
    return manifest


def api_origin(base_url: str) -> str:
    parsed = urlsplit(base_url)
    host = parsed.hostname
    if not host or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("--base-url must be a bare API origin")
    if parsed.scheme == "https":
        return f"https://{parsed.netloc}"
    if parsed.scheme == "http":
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        if loopback:
            return f"http://{parsed.netloc}"
    raise ValueError("--base-url requires HTTPS, except HTTP on loopback")


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def prepared_seeds(seed_file: Path) -> list[dict]:
    seeds = json.loads(seed_file.read_text(encoding="utf-8"))
    if not isinstance(seeds, list) or len(seeds) != 2:
        raise ValueError("expected exactly two reviewed feed seeds")
    urls = {
        "https://huggingface.co/blog/feed.xml",
        "https://github.com/groq/groq-changelog/commits/main.atom",
    }
    if {seed.get("feed_url") for seed in seeds} != urls:
        raise ValueError("unreviewed feed seed URL")
    for seed in seeds:
        if seed.get("enabled") is not False or seed.get("channel_type") != "rss":
            raise ValueError("seed must remain a disabled RSS candidate")
    return seeds


def apply_seeds(base_url: str, token: str, seed_file: Path) -> None:
    origin = api_origin(base_url)
    seeds = prepared_seeds(seed_file)
    opener = build_opener(
        RejectRedirects(), HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def request(path: str, *, method: str = "GET", body: dict | None = None, csrf: str = "") -> dict:
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        req = Request(origin + path, data=payload, headers=headers, method=method)
        with opener.open(req, timeout=15) as response:
            return json.load(response)

    login = request("/api/v1/admin/session", method="POST", body={"token": token})
    csrf = login["csrf_token"]
    existing = request("/api/v1/admin/sources")["items"]
    known_urls = {row["feed_url"].rstrip("/") for row in existing}
    known_names = {row["name"] for row in existing}
    for seed in seeds:
        if seed["feed_url"].rstrip("/") in known_urls or seed["name"] in known_names:
            print(f"skip existing: {seed['name']}")
            continue
        payload = {key: seed[key] for key in ("name", "feed_url", "channel_type")}
        created = request("/api/v1/admin/sources", method="POST", body=payload, csrf=csrf)
        if created["enabled"] is not False:
            raise RuntimeError(f"source unexpectedly enabled: {seed['name']}")
        print(f"created disabled: {seed['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--apply-seeds", action="store_true", help="Explicitly create only missing, disabled seeds via admin API")
    parser.add_argument("--apply-prepared", action="store_true", help="Use checked packaged data without the external reference folder")
    parser.add_argument("--base-url", help="HTTPS API origin, or HTTP loopback origin")
    args = parser.parse_args()
    manifest = checked_prepared(args.output) if args.apply_prepared else prepare(args.reference, args.output)
    print(json.dumps(manifest["row_counts"], ensure_ascii=False))
    if args.apply_seeds:
        token = os.environ.get("RADAR_ADMIN_TOKEN")
        if not args.base_url or not token:
            parser.error("--apply-seeds requires --base-url and RADAR_ADMIN_TOKEN")
        try:
            apply_seeds(args.base_url, token, args.output / "disabled_feed_seeds.json")
        except HTTPError as exc:
            raise SystemExit(f"admin source API returned HTTP {exc.code}") from exc


if __name__ == "__main__":
    main()
