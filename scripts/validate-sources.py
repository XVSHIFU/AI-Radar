"""Read-only RSS candidate probes. Success here does not prove article extraction."""
import concurrent.futures
import datetime
import json
import pathlib
import urllib.request
import xml.etree.ElementTree as ET

CANDIDATES = [
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("Google Research", "https://research.google/blog/rss/"),
    ("AWS Machine Learning", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("NVIDIA Technical Blog", "https://developer.nvidia.com/blog/feed/"),
]


def probe(candidate):
    name, url = candidate
    result = {"name": name, "feed_url": url, "feed_status": "failed", "body_validation": "not_run", "validated_events": 0}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AI-Radar-SourceValidation/0.1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError("feed exceeds 2 MB limit")
            result["http_status"] = response.status
            root = ET.fromstring(body)
        entries = root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
        if not entries:
            raise ValueError("no RSS/Atom entries")
        result.update(feed_status="parsed", entry_count=len(entries))
        samples = []
        for entry in entries[:3]:
            title = entry.findtext("title") or entry.findtext("{http://www.w3.org/2005/Atom}title")
            link = entry.findtext("link")
            if not link:
                atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
                link = atom_link.get("href") if atom_link is not None else None
            samples.append({"title": title, "url": link, "published": entry.findtext("pubDate") or entry.findtext("{http://www.w3.org/2005/Atom}published")})
        result["samples"] = samples
    except Exception as exc:
        result["error"] = str(exc)
    return result


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(probe, CANDIDATES))
    report = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "layer": "live_feed_probe_only", "sources": results, "parsed_feeds": sum(r["feed_status"] == "parsed" for r in results), "fully_validated_sources": 0, "real_standard_events": 0}
    target = pathlib.Path(__file__).resolve().parents[1] / "docs" / "source-validation.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(target), "parsed_feeds": report["parsed_feeds"], "fully_validated_sources": 0}))
