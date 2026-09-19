import asyncio
import hashlib
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser  # type: ignore[import-untyped]
import httpx

from .public_transport import is_public_address

TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
MAX_REDIRECTS = 5


class UnsafeUrl(ValueError):
    pass


class ResponseTooLarge(ValueError):
    pass


class DocumentParseError(ValueError):
    pass


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise UnsafeUrl("only absolute http(s) URLs are allowed")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrl("URL userinfo is not allowed")
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_KEYS and not key.casefold().startswith("utm_")
    ]
    port = parts.port
    host = parts.hostname.casefold()
    rendered_host = f"[{host}]" if ":" in host else host
    netloc = f"{rendered_host}:{port}" if port else rendered_host
    return urlunsplit((parts.scheme.casefold(), netloc, parts.path or "/", urlencode(query), ""))


def _is_public(address: str) -> bool:
    return is_public_address(address)


async def resolve_public(
    value: str,
    resolver: Callable[[str], Awaitable[list[str]]] | None = None,
) -> None:
    host = urlsplit(canonicalize_url(value)).hostname
    assert host is not None
    if resolver:
        addresses = await resolver(host)
    else:
        records = await asyncio.to_thread(socket.getaddrinfo, host, None)
        addresses = list({str(record[4][0]) for record in records})
    if not addresses or any(not _is_public(address) for address in addresses):
        raise UnsafeUrl("URL resolves to a non-public address")


@dataclass(frozen=True)
class FetchResult:
    status: int
    final_url: str
    body: bytes
    etag: str | None
    last_modified: str | None


async def fetch_public(
    client: httpx.AsyncClient,
    url: str,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    resolver: Callable[[str], Awaitable[list[str]]] | None = None,
) -> FetchResult:
    current = canonicalize_url(url)
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    for _ in range(MAX_REDIRECTS + 1):
        await resolve_public(current, resolver)
        async with client.stream("GET", current, headers=headers, timeout=20) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise UnsafeUrl("redirect has no location")
                current = canonicalize_url(urljoin(current, location))
                continue
            if response.status_code == 304:
                return FetchResult(
                    304,
                    current,
                    b"",
                    response.headers.get("etag"),
                    response.headers.get("last-modified"),
                )
            response.raise_for_status()
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise ResponseTooLarge(f"response exceeds {max_bytes} bytes")
                chunks.append(chunk)
            return FetchResult(
                response.status_code,
                current,
                b"".join(chunks),
                response.headers.get("etag"),
                response.headers.get("last-modified"),
            )
    raise UnsafeUrl("too many redirects")


@dataclass(frozen=True)
class FeedEntry:
    title: str
    url: str
    original_url: str
    published: str | None
    excerpt: str | None = None
    tags: tuple[str, ...] = ()


class SummaryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored:
            self.parts.append(data)


def feed_excerpt(value: str | None) -> str | None:
    if not value:
        return None
    parser = SummaryParser()
    parser.feed(value)
    cleaned = " ".join(" ".join(parser.parts).split())[:600]
    return cleaned or None


def parse_feed(body: bytes) -> list[FeedEntry]:
    parsed = feedparser.parse(body)
    if parsed.bozo and not parsed.entries:
        raise ValueError("invalid RSS/Atom document")
    return [
        FeedEntry(
            str(entry.get("title", "")).strip(),
            canonicalize_url(str(entry.link)),
            str(entry.link),
            entry.get("published") or entry.get("updated"),
            feed_excerpt(entry.get("summary")),
            tuple(
                str(tag.get("term", "")).strip() for tag in entry.get("tags", []) if tag.get("term")
            ),
        )
        for entry in parsed.entries
        if entry.get("link")
    ]


class ParagraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.buffer: list[str] = []
        self.paragraphs: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer"}:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag in {"p", "li", "h1", "h2", "h3"}:
            self.depth += 1
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.depth and not self.ignored_depth:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and tag in {"p", "li", "h1", "h2", "h3"} and self.depth:
            text = " ".join("".join(self.buffer).split())
            if text:
                self.paragraphs.append(text)
            self.depth -= 1
            self.buffer = []


@dataclass(frozen=True)
class ParsedDocument:
    paragraphs: dict[str, str]
    content_hash: str
    parser_version: str = "stdlib-html-v1"


def parse_document(body: bytes) -> ParsedDocument:
    parser = ParagraphParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    paragraphs = {
        f"p-{index:04d}-{hashlib.sha256(text.encode()).hexdigest()[:12]}": text
        for index, text in enumerate(parser.paragraphs, 1)
    }
    normalized = "\n".join(paragraphs.values())
    if not normalized:
        raise DocumentParseError("document contains no extractable paragraphs")
    return ParsedDocument(paragraphs, hashlib.sha256(normalized.encode()).hexdigest())


def validate_quote(paragraphs: dict[str, str], paragraph_id: str, quote: str) -> None:
    if not quote:
        raise ValueError("quote must not be empty")
    paragraph = paragraphs.get(paragraph_id)
    if paragraph is None or quote not in paragraph:
        raise ValueError("quote is not locatable in the frozen paragraph")


def validate_citation_whitelist(cited_ids: list[str], allowed_ids: set[str]) -> None:
    if len(cited_ids) != len(set(cited_ids)) or not set(cited_ids) <= allowed_ids:
        raise ValueError("citation list contains duplicate or non-whitelisted evidence")
