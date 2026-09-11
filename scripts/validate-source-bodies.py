"""Read-only live feed/body probe using the production fetch/parser path; never publishes."""
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from radar.ingest.core import (
    fetch_public,
    parse_document,
    parse_feed,
    validate_quote,
)
from radar.ingest.public_transport import PublicAsyncTransport
from validate_sources_catalog import SOURCES


async def probe(name: str, url: str) -> dict:
    result = {"name": name, "feed_url": url, "feed_status": "failed", "body_status": "not_run"}
    async with httpx.AsyncClient(
        transport=PublicAsyncTransport(), follow_redirects=False, trust_env=False,
        headers={"User-Agent": "AI-Radar-SourceValidation/0.1"},
    ) as client:
        try:
            feed = await asyncio.wait_for(fetch_public(client, url, max_bytes=2_000_000), 45)
            entries = parse_feed(feed.body)
            result.update(feed_status="parsed", feed_http_status=feed.status, entry_count=len(entries))
            if not entries:
                raise ValueError("feed contains no entries")
            entry = entries[0]
            result.update(article_title=entry.title, article_url=entry.url, source_published=entry.published)
            fetched = await asyncio.wait_for(fetch_public(client, entry.url), 45)
            document = parse_document(fetched.body)
            # This checks only local paragraph addressing, not semantic relevance or extracted events.
            paragraph_id, text = next(iter(document.paragraphs.items()))
            validate_quote(document.paragraphs, paragraph_id, text[:80])
            result.update(
                body_status="parsed", article_http_status=fetched.status,
                final_url=fetched.final_url, bytes=len(fetched.body),
                paragraph_count=len(document.paragraphs),
                parser_version=document.parser_version, content_hash=document.content_hash,
                paragraph_locator_check=True,
            )
        except (httpx.HTTPError, ValueError, OSError, TimeoutError) as exc:
            if result["feed_status"] == "parsed":
                result["body_status"] = "failed"
            result["error_type"] = type(exc).__name__
            result["error"] = str(exc)[:500]
    return result


async def main() -> None:
    started = datetime.now(UTC)
    results = await asyncio.gather(*(probe(name, url) for name, url in SOURCES))
    report = {
        "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(),
        "layer": "live_feed_and_body_parser_no_database_no_model",
        "sources": results, "parsed_feeds": sum(x["feed_status"] == "parsed" for x in results),
        "parsed_body_samples": sum(x["body_status"] == "parsed" for x in results),
        "database_writes": 0, "model_calls": 0, "real_standard_events": 0,
        "fully_validated_sources": 0,
        "limitations": [
            "One latest article per source; paragraph extraction is not semantic article quality.",
            "No database persistence, extraction model, event publication, or real Evidence acceptance.",
            "Article body text is not retained in this report.",
        ],
    }
    target = ROOT / "docs" / "source-body-validation.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("parsed_feeds", "parsed_body_samples", "real_standard_events")}))


if __name__ == "__main__":
    asyncio.run(main())
