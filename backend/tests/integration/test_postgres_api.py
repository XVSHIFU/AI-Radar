import asyncio
import json
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from radar.config import get_settings
from radar.main import app

pytestmark = pytest.mark.postgres


@contextmanager
def _client(database: Any, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RADAR_DATA_MODE", "postgres")
    monkeypatch.setenv("DATABASE_URL", database.rendered_url)
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


async def _seed_retrieval(database: Any) -> dict[str, UUID]:
    ids = {
        name: uuid4()
        for name in (
            "source",
            "article",
            "version",
            "entity",
            "alias",
            "first",
            "second",
            "draft",
            "mention",
            "evidence",
            "invalid_evidence",
        )
    }
    connection = await database.connect()
    try:
        await connection.execute(
            "INSERT INTO sources "
            "(id, name, feed_url, enabled, health, consecutive_failures, "
            "canonical_host, channel_type) "
            "VALUES ($1, $2, $3, true, 'healthy', 0, $4, 'rss')",
            ids["source"],
            f"retrieval-{ids['source']}",
            "https://example.com/feed",
            "example.com",
        )
        await connection.execute(
            "INSERT INTO articles (id, source_id, canonical_url) VALUES ($1, $2, $3)",
            ids["article"],
            ids["source"],
            f"https://example.com/{ids['article']}",
        )
        paragraphs = {"p-0001": "DeepSeek released a verifiable research system."}
        await connection.execute(
            "INSERT INTO article_versions "
            "(id, article_id, title, source_url, published_at, paragraphs, content_hash) "
            "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)",
            ids["version"],
            ids["article"],
            "Frozen source",
            f"https://example.com/{ids['article']}",
            datetime(2026, 9, 10, 3, 0, tzinfo=UTC),
            json.dumps(paragraphs),
            uuid4().hex + uuid4().hex,
        )
        await connection.execute(
            "INSERT INTO entities (id, canonical_name, entity_type) VALUES ($1, $2, 'company')",
            ids["entity"],
            f"DeepSeek-{ids['entity']}",
        )
        await connection.execute(
            "INSERT INTO entity_aliases (id, entity_id, normalized_alias, alias_source) "
            "VALUES ($1, $2, 'deepseek-live', 'curated')",
            ids["alias"],
            ids["entity"],
        )
        for event_id, event_date, status, role in (
            (ids["first"], date(2026, 9, 10), "published", "subject"),
            (ids["second"], date(2026, 9, 9), "published", "product"),
            (ids["draft"], date(2026, 9, 8), "needs_review", "subject"),
            (ids["mention"], date(2026, 9, 7), "published", "mention"),
        ):
            await connection.execute(
                "INSERT INTO events "
                "(id, title_zh, summary_zh, category, importance, event_date, "
                "date_precision, date_basis, status, source_count, "
                "evidence_count, content_version) "
                "VALUES ($1, $2, $3, 'research', 5, $4::date, 'day', 'explicit_body', $5, 1, 1, 1)",
                event_id,
                f"Event {event_id}",
                "Database-backed evidence",
                event_date,
                status,
            )
            await connection.execute(
                "INSERT INTO event_entities (event_id, entity_id, role) VALUES ($1, $2, $3)",
                event_id,
                ids["entity"],
                role,
            )
        await connection.execute(
            "INSERT INTO evidence "
            "(id, event_id, article_version_id, paragraph_id, quote_text, verification_status) "
            "VALUES ($1, $2, $3, 'p-0001', $4, 'unverified')",
            ids["evidence"],
            ids["first"],
            ids["version"],
            "verifiable research system",
        )
        await connection.execute(
            "INSERT INTO evidence "
            "(id, event_id, article_version_id, paragraph_id, quote_text, verification_status) "
            "VALUES ($1, $2, $3, 'p-0001', 'invented quote', 'unverified')",
            ids["invalid_evidence"],
            ids["second"],
            ids["version"],
        )
    finally:
        await connection.close()
    return ids


def test_health_ready_checks_real_migration_and_vector(
    postgres_database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _client(postgres_database, monkeypatch) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "data_mode": "postgres",
        "synthetic": False,
        "postgres_ready": True,
    }


def test_exact_filters_pagination_and_frozen_evidence(
    postgres_database: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = asyncio.run(_seed_retrieval(postgres_database))
    params = {
        "q": "deepseek-live",
        "category": "research",
        "date_from": "2026-09-01",
        "date_to": "2026-09-30",
        "limit": 1,
    }
    with _client(postgres_database, monkeypatch) as client:
        first = client.get("/api/v1/events", params=params)
        first_body = first.json()
        second = client.get(
            "/api/v1/events", params={**params, "cursor": first_body["next_cursor"]}
        )
        evidence = client.get(f"/api/v1/events/{ids['first']}/evidence")
        invalid = client.get(f"/api/v1/events/{ids['second']}/evidence")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first_body["total"] == 2
    assert second.json()["total"] == 2
    assert {first_body["items"][0]["id"], second.json()["items"][0]["id"]} == {
        str(ids["first"]),
        str(ids["second"]),
    }
    assert second.json()["next_cursor"] is None
    assert evidence.status_code == 200
    assert evidence.json()["items"][0]["quote_text"] == "verifiable research system"
    assert evidence.json()["items"][0]["article_version_id"] == str(ids["version"])
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "EVIDENCE_INVALID"
