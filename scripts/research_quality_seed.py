"""Install the frozen corpus into an EMPTY, already migrated disposable test DB.

Never reads application Settings or DATABASE_URL, never creates/drops databases,
and never replaces existing rows. Operators must supply RADAR_QUALITY_DATABASE_URL.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
from datetime import date
from uuid import UUID, uuid5

import asyncpg
from radar.normalize import normalize_text
from radar.retrieval import SEARCH_CONFIG_VERSION, search_document
from research_quality import CORPUS, validate
from sqlalchemy import make_url
from sqlalchemy.exc import ArgumentError

TEST_NAME = re.compile(r"radar_test_[0-9a-f]{32}\Z")


def connection_parameters(rendered):
    try:
        url = make_url(rendered)
        if (
            url.drivername not in {"postgresql", "postgresql+asyncpg"}
            or url.host not in {"127.0.0.1", "localhost", "::1"}
            or not TEST_NAME.fullmatch(url.database or "")
            or url.query
        ):
            raise ValueError
        return {
            "host": url.host,
            "port": url.port or 5432,
            "database": url.database,
            "user": url.username,
            "password": url.password,
            "timeout": 5,
        }
    except (ArgumentError, TypeError, ValueError):
        raise ValueError(
            "explicit loopback radar_test_<32 hex> database required"
        ) from None


def seed_batches(corpus):
    validate(corpus)
    batches = {
        name: []
        for name in (
            "entities",
            "entity_aliases",
            "events",
            "event_entities",
            "sources",
            "articles",
            "article_versions",
            "event_articles",
            "evidence",
        )
    }
    for entity in corpus["entities"]:
        identifier = UUID(entity["id"])
        batches["entities"].append((identifier, entity["name"], entity["type"]))
        for alias in dict.fromkeys(normalize_text(a) for a in entity["aliases"]):
            batches["entity_aliases"].append(
                (uuid5(identifier, alias), identifier, alias)
            )
    for item in corpus["events"]:
        identifier = UUID(item["id"])
        quotes = [e["quote_text"] for e in item["evidence"]]
        batches["events"].append(
            (
                identifier,
                item["title"],
                quotes[0],
                item["category"],
                date.fromisoformat(item["event_date"]) if item["event_date"] else None,
                item["date_precision"],
                item["date_basis"],
                item["date_conflict"],
                len(quotes),
                len(quotes),
                item["content_version"],
                search_document(item["title"], item["entity"], *quotes),
                SEARCH_CONFIG_VERSION,
            )
        )
        batches["event_entities"].append((identifier, UUID(item["entity_id"])))
        for index, evidence in enumerate(item["evidence"]):
            evidence_id = UUID(evidence["id"])
            source_id, article_id = (
                uuid5(evidence_id, "source"),
                uuid5(evidence_id, "article"),
            )
            version_id = UUID(evidence["article_version_id"])
            paragraphs = {evidence["paragraph_id"]: evidence["quote_text"]}
            batches["sources"].append(
                (source_id, f"quality-v1-{evidence_id}", evidence["source_url"])
            )
            batches["articles"].append((article_id, source_id, evidence["source_url"]))
            batches["article_versions"].append(
                (
                    version_id,
                    article_id,
                    item["title"],
                    evidence["source_url"],
                    json.dumps(paragraphs, ensure_ascii=False),
                    hashlib.sha256(evidence["quote_text"].encode()).hexdigest(),
                )
            )
            batches["event_articles"].append((identifier, article_id, index == 0))
            batches["evidence"].append(
                (
                    evidence_id,
                    identifier,
                    version_id,
                    evidence["paragraph_id"],
                    evidence["quote_text"],
                    evidence["quote_sha256"],
                )
            )
    return batches


# Fixed SQL, only frozen values supplied as parameters. No model-authored SQL.
INSERTS = {
    "entities": "INSERT INTO entities (id,canonical_name,entity_type) VALUES ($1,$2,$3)",
    "entity_aliases": "INSERT INTO entity_aliases (id,entity_id,normalized_alias,alias_source) "
    "VALUES ($1,$2,$3,'curated')",
    "events": "INSERT INTO events (id,title_zh,summary_zh,category,importance,event_date,"
    "date_precision,date_basis,date_conflict,status,source_count,evidence_count,"
    "content_version,search_document,search_config_version) "
    "VALUES ($1,$2,$3,$4,3,$5,$6,$7,$8,'published',$9,$10,$11,$12,$13)",
    "event_entities": "INSERT INTO event_entities (event_id,entity_id,role) "
    "VALUES ($1,$2,'subject')",
    "sources": "INSERT INTO sources (id,name,feed_url,enabled,health,consecutive_failures,"
    "canonical_host,channel_type) "
    "VALUES ($1,$2,$3,false,'unknown',0,'example.invalid','rss')",
    "articles": "INSERT INTO articles (id,source_id,canonical_url) VALUES ($1,$2,$3)",
    "article_versions": "INSERT INTO article_versions (id,article_id,title,source_url,paragraphs,"
    "content_hash) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
    "event_articles": "INSERT INTO event_articles (event_id,article_id,relation_type,is_primary) "
    "VALUES ($1,$2,'supports',$3)",
    "evidence": "INSERT INTO evidence (id,event_id,article_version_id,paragraph_id,quote_text,"
    "quote_hash,support_type,verification_status) "
    "VALUES ($1,$2,$3,$4,$5,$6,'direct','unverified')",
}


async def seed(connection, expected_database, corpus):
    if not TEST_NAME.fullmatch(expected_database):
        raise ValueError("disposable database name required")
    batches = seed_batches(corpus)
    if await connection.fetchval("SELECT current_database()") != expected_database:
        raise ValueError("connected database does not match disposable target")
    async with connection.transaction():
        await connection.execute("SET LOCAL lock_timeout = '3s'")
        await connection.execute("SET LOCAL statement_timeout = '15s'")
        revision = await connection.fetchval("SELECT version_num FROM alembic_version")
        if revision != "0013_public_quota_retention":
            raise ValueError(
                "quality database must be migrated to the candidate schema"
            )
        # No concurrent loader or collector may invalidate the emptiness check.
        await connection.execute(
            "LOCK TABLE events, entities, entity_aliases, sources, articles, article_versions, "
            "event_articles, event_entities, evidence, public_ask_requests, llm_calls "
            "IN ACCESS EXCLUSIVE MODE"
        )
        for table in (*INSERTS, "public_ask_requests", "llm_calls"):
            if await connection.fetchval(f"SELECT EXISTS (SELECT 1 FROM {table})"):
                raise ValueError("quality database is not empty; no rows were changed")
        for table, statement in INSERTS.items():
            await connection.executemany(statement, batches[table])
        return {
            "status": "seeded",
            "corpus_sha256": corpus["content_sha256"],
            "counts": {table: len(rows) for table, rows in batches.items()},
        }


async def install(rendered, corpus):
    parameters = connection_parameters(rendered)
    validate(corpus)
    connection = await asyncpg.connect(**parameters)
    try:
        return await seed(connection, parameters["database"], corpus)
    finally:
        await connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install", action="store_true", help="write only to an empty test database"
    )
    args = parser.parse_args()
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    if args.install:
        rendered = os.environ.get("RADAR_QUALITY_DATABASE_URL")
        if not rendered:
            raise SystemExit(
                "RADAR_QUALITY_DATABASE_URL must name an explicit disposable database"
            )
        try:
            result = asyncio.run(install(rendered, corpus))
        except Exception:  # noqa: BLE001 -- redact credentials at the operator CLI boundary
            # Connection errors can embed DSNs; do not echo secrets through a traceback.
            raise SystemExit(
                "quality seed failed; no configuration or database credentials printed"
            ) from None
    else:
        result = {
            "status": "dry_run",
            "counts": {
                table: len(rows) for table, rows in seed_batches(corpus).items()
            },
            "corpus_sha256": corpus["content_sha256"],
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
