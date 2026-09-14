"""Small adapters for dated entries in official source archives."""

import json
import re
from datetime import UTC, date, datetime, time, timedelta
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin
from zoneinfo import ZoneInfo

from .core import FeedEntry, canonicalize_url
from .dates import published_datetime

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


def entry_day(entry: FeedEntry) -> date | None:
    value = entry.published or ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    instant = published_datetime(value)
    return instant.astimezone(BUSINESS_TZ).date() if instant else None


def in_range(entry: FeedEntry, start: date, end: date) -> bool:
    day = entry_day(entry)
    return day is not None and start <= day <= end


class TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def text_only(html: str) -> str:
    parser = TextOnly()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def parse_aws_archive(body: bytes) -> list[FeedEntry]:
    html = body.decode("utf-8", errors="replace")
    cards = re.findall(
        r'<h2\b[^>]*class="[^"]*blog-post-title[^"]*"[^>]*>(.*?)</h2>'
        r'(.*?)(?=<h2\b[^>]*class="[^"]*blog-post-title|$)',
        html,
        re.S,
    )
    entries = []
    for heading, rest in cards:
        link = re.search(r'href="([^"]+)"', heading)
        timestamp = re.search(r'<time\b[^>]*datetime="([^"]+)"', rest)
        if link and timestamp:
            url = canonicalize_url(urljoin("https://aws.amazon.com", unescape(link[1])))
            entries.append(FeedEntry(text_only(heading), url, url, unescape(timestamp[1])))
    return entries


def parse_anthropic_archive(body: bytes) -> list[FeedEntry]:
    html = body.decode("utf-8", errors="replace")
    payload = html
    for _ in range(3):
        payload = payload.replace("\\\\", "\\").replace('\\"', '"')
    dates = {
        slug: stamp
        for stamp, slug in re.findall(
            r'"publishedOn":"([^"]+)".{0,500}?"current":"([^"]+)"',
            payload,
        )
        if published_datetime(stamp)
    }
    entries: dict[str, FeedEntry] = {}
    chunks = []
    prefix = "self.__next_f.push("
    for script in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S):
        if not script.startswith(prefix) or not script.endswith(")"):
            continue
        try:
            chunk = json.loads(script[len(prefix) : -1])
            if len(chunk) == 2 and chunk[0] == 1 and isinstance(chunk[1], str):
                chunks.append(chunk[1])
        except (ValueError, TypeError):
            continue
    stream = "".join(chunks)
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"_type":"post"', stream):
        try:
            post, _ = decoder.raw_decode(stream, match.start())
            if not any(d.get("value") == "news" for d in post.get("directories", [])):
                continue
            stamp, slug, title = post["publishedOn"], post["slug"]["current"], post["title"]
            if not published_datetime(stamp):
                continue
            url = canonicalize_url("https://www.anthropic.com/news/" + slug)
            entries[url] = FeedEntry(title, url, url, stamp)
        except (KeyError, TypeError, ValueError):
            continue
    for path, inner in re.findall(r'<a\b[^>]*href="(/news/[^"]+)"[^>]*>(.*?)</a>', html, re.S):
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        if slug not in dates:
            continue
        title = re.search(
            r'<(?:span|h[1-6])\b[^>]*class="[^"]*__title[^"]*"[^>]*>(.*?)</(?:span|h[1-6])>',
            inner,
            re.S,
        )
        name = text_only(title[1] if title else inner)
        if not name:
            continue
        url = canonicalize_url(urljoin("https://www.anthropic.com", path))
        entries[url] = FeedEntry(name, url, url, dates[slug])
    return list(entries.values())


def parse_deepseek_archive(body: bytes) -> list[FeedEntry]:
    html = body.decode("utf-8", errors="replace")
    entries: dict[str, FeedEntry] = {}
    # The dated release URLs are official changelog links, not inferred web-search dates.
    for stamp in re.findall(r'href="/news/news(\d{6})"', html):
        try:
            day = datetime.strptime(stamp, "%y%m%d").date()
        except ValueError:
            continue
        if f"Date: {day.isoformat()}" not in html:
            continue
        url = f"https://api-docs.deepseek.com/news/news{stamp}"
        entries[url] = FeedEntry(
            f"DeepSeek 官方更新 {day.isoformat()}",
            url,
            url,
            day.isoformat(),
        )
    return list(entries.values())


def arxiv_query(start: date, end: date, offset: int, page_size: int = 200) -> str:
    lower = datetime.combine(start, time.min, BUSINESS_TZ).astimezone(UTC)
    upper = datetime.combine(end + timedelta(days=1), time.min, BUSINESS_TZ).astimezone(UTC)
    upper -= timedelta(minutes=1)
    query = f"cat:cs.AI AND submittedDate:[{lower:%Y%m%d%H%M} TO {upper:%Y%m%d%H%M}]"
    return "https://export.arxiv.org/api/query?" + urlencode(
        {
            "search_query": query,
            "start": offset,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
        }
    )
