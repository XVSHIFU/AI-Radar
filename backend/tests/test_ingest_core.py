from decimal import Decimal
from typing import cast

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from radar.ingest.core import (
    ResponseTooLarge,
    UnsafeUrl,
    canonicalize_url,
    fetch_public,
    parse_document,
    validate_citation_whitelist,
    validate_quote,
)
from radar.ingest_repository import BudgetUnavailable, IngestRepository


async def public_resolver(_host: str) -> list[str]:
    return ["93.184.216.34"]


def test_canonical_url_removes_only_known_tracking_parameters() -> None:
    value = canonicalize_url(
        "https://Examplefinder.com/x?utm_source=a&id=7&token=X&fbclid=z#fragment"
    )
    assert value == "https://examplefinder.com/x?id=7&token=X"


@pytest.mark.asyncio
async def test_conditional_304_sends_validators() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["if-none-match"] == '"v1"'
        assert request.headers["if-modified-since"] == "yesterday"
        return httpx.Response(304, headers={"etag": '"v1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_public(
            client,
            "https://examplefinder.com/feed",
            etag='"v1"',
            last_modified="yesterday",
            resolver=public_resolver,
        )
    assert result.status == 304
    assert result.body == b""


@pytest.mark.asyncio
async def test_private_redirect_is_rejected_after_dns_resolution() -> None:
    async def resolver(host: str) -> list[str]:
        return ["127.0.0.1"] if host == "localhost" else ["93.184.216.34"]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://localhost/secret"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UnsafeUrl):
            await fetch_public(
                client,
                "https://examplefinder.com/feed",
                resolver=resolver,
            )


@pytest.mark.asyncio
async def test_response_size_limit_is_enforced() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"123456")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ResponseTooLarge):
            await fetch_public(
                client,
                "https://examplefinder.com/feed",
                max_bytes=5,
                resolver=public_resolver,
            )


def test_document_hash_and_paragraph_ids_are_deterministic() -> None:
    first = parse_document(b"<h1>Title</h1><p>Frozen paragraph.</p>")
    second = parse_document(b"<h1>Title</h1><p>Frozen paragraph.</p>")
    assert first == second
    paragraph_id = next(key for key, value in first.paragraphs.items() if "Frozen" in value)
    validate_quote(first.paragraphs, paragraph_id, "Frozen paragraph")
    with pytest.raises(ValueError):
        validate_quote(first.paragraphs, paragraph_id, "invented quote")


def test_citation_whitelist_rejects_unknown_and_duplicates() -> None:
    validate_citation_whitelist(["e1"], {"e1", "e2"})
    with pytest.raises(ValueError):
        validate_citation_whitelist(["e1", "e1"], {"e1"})
    with pytest.raises(ValueError):
        validate_citation_whitelist(["e3"], {"e1"})


@pytest.mark.asyncio
async def test_unconfigured_budget_is_rejected_before_database_access() -> None:
    sessions = cast(async_sessionmaker[AsyncSession], None)
    repository = IngestRepository(sessions)
    with pytest.raises(BudgetUnavailable):
        await repository.reserve_budget("daily-total", "request-1", Decimal("1.00"), None)


def test_parser_rejects_empty_and_ignores_non_content_regions() -> None:
    with pytest.raises(ValueError):
        parse_document(b"<html><script>fake</script><nav><p>menu</p></nav></html>")
    document = parse_document(b"<nav><p>menu</p></nav><main><p>real body</p></main>")
    assert list(document.paragraphs.values()) == ["real body"]
    with pytest.raises(ValueError):
        validate_quote(document.paragraphs, next(iter(document.paragraphs)), "")
