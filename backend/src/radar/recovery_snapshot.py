"""Read-only, operator-owned PostgreSQL snapshot and recovery comparisons.

No connection defaults or model-facing tool registration. The caller supplies a
trusted engine and must run pg_dump with the yielded snapshot ID before leaving
the context. This module does not itself create a dump or authorize promotion.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .recovery_bundle import FINGERPRINT_TABLES, HASH, InvalidBundle

SNAPSHOT_ID = re.compile(r"[0-9A-F]{8}-[0-9A-F]{8}-[0-9]+\Z")
ORDER_BY = {
    "public_ask_requests": "id",
    "research_model_calls": "run_id, sequence",
    "llm_calls": "id",
    "budget_reservations": "id",
    "events": "id",
    "evidence": "id",
}
MAX_ROW_BYTES = 16 * 1024 * 1024


class Fingerprint(TypedDict):
    rows: int
    sha256: str


class Snapshot(TypedDict):
    schema: str
    captured_at: str
    snapshot_id: str
    fingerprints: dict[str, Fingerprint]


class TableDigest:
    """Hash row boundaries as well as values; never retain row contents."""

    def __init__(self, table: str) -> None:
        if table not in FINGERPRINT_TABLES:
            raise InvalidBundle("unknown recovery table")
        self._digest = hashlib.sha256(b"radar-row-jsonb/1\x00" + table.encode() + b"\x00")
        self._rows = 0

    def add(self, value: str) -> None:
        if not isinstance(value, str):
            raise InvalidBundle("invalid recovery row")
        raw = value.encode("utf-8")
        if len(raw) > MAX_ROW_BYTES:
            raise InvalidBundle("recovery row exceeds capture limit")
        self._digest.update(len(raw).to_bytes(8, "big"))
        self._digest.update(raw)
        self._rows += 1

    def finish(self) -> Fingerprint:
        return {"rows": self._rows, "sha256": self._digest.hexdigest()}


def compare_fingerprints(expected: Any, actual: Mapping[str, Fingerprint]) -> None:
    if not isinstance(expected, dict) or set(expected) != FINGERPRINT_TABLES:
        raise InvalidBundle("incomplete recovery fingerprints")
    if set(actual) != FINGERPRINT_TABLES:
        raise InvalidBundle("incomplete restored fingerprints")
    for table in sorted(FINGERPRINT_TABLES):
        record = expected[table]
        if (
            not isinstance(record, dict)
            or set(record) != {"rows", "sha256"}
            or type(record["rows"]) is not int
            or record["rows"] < 0
            or not isinstance(record["sha256"], str)
            or not HASH.fullmatch(record["sha256"])
        ):
            raise InvalidBundle("invalid expected fingerprint")
        if record != actual[table]:
            # No row, key, owner, IP hash or transcript is included in errors.
            raise InvalidBundle("restored fingerprint mismatch: " + table)


@asynccontextmanager
async def _transaction(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    # Deadline also covers the caller's dump while the exported snapshot is held.
    async with asyncio.timeout(1800), engine.connect() as connection:
        await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            for setting in (
                "SET LOCAL TIME ZONE 'UTC'",
                "SET LOCAL DateStyle TO 'ISO, YMD'",
                "SET LOCAL IntervalStyle TO 'iso_8601'",
                "SET LOCAL extra_float_digits TO 3",
                "SET LOCAL search_path TO pg_catalog",
                "SET LOCAL lock_timeout TO '5s'",
                "SET LOCAL statement_timeout TO '120s'",
                "SET LOCAL idle_in_transaction_session_timeout TO '30min'",
            ):
                await connection.execute(text(setting))
            tables = ", ".join("public." + name for name in sorted(FINGERPRINT_TABLES))
            await connection.execute(
                text("LOCK TABLE public.alembic_version, " + tables + " IN ACCESS SHARE MODE")
            )
            revisions = (
                (await connection.execute(text("SELECT version_num FROM public.alembic_version")))
                .scalars()
                .all()
            )
            if revisions != ["0013_public_quota_retention"]:
                raise InvalidBundle("unsupported recovery schema")
            yield connection


async def _fingerprints(connection: AsyncConnection) -> dict[str, Fingerprint]:
    result: dict[str, Fingerprint] = {}
    for table, order in sorted(ORDER_BY.items()):
        digest = TableDigest(table)
        # Only fixed identifiers enter SQL. PostgreSQL jsonb text and UTC output
        # are compared using the same pinned database image after restoration.
        query = text(
            "SELECT CASE WHEN octet_length(to_jsonb(t)::text) <= :limit "
            "THEN to_jsonb(t)::text ELSE NULL END FROM public." + table + " AS t ORDER BY " + order
        )
        async with connection.stream(query, {"limit": MAX_ROW_BYTES}) as rows:
            async for row in rows:
                digest.add(row[0])
        result[table] = digest.finish()
    return result


@asynccontextmanager
async def capture_snapshot(engine: AsyncEngine) -> AsyncIterator[Snapshot]:
    async with _transaction(engine) as connection:
        snapshot = await connection.scalar(text("SELECT pg_export_snapshot()"))
        captured_at = await connection.scalar(text("SELECT transaction_timestamp()"))
        if not isinstance(snapshot, str) or not SNAPSHOT_ID.fullmatch(snapshot):
            raise InvalidBundle("invalid exported snapshot")
        if not isinstance(captured_at, datetime) or captured_at.tzinfo is None:
            raise InvalidBundle("invalid snapshot time")
        yield {
            "schema": "0013",
            "captured_at": captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "snapshot_id": snapshot,
            "fingerprints": await _fingerprints(connection),
        }


async def verify_restored_snapshot(engine: AsyncEngine, expected: Any) -> None:
    """Compare a restored, offline DB; does not start writers or promote it."""
    async with _transaction(engine) as connection:
        compare_fingerprints(expected, await _fingerprints(connection))
