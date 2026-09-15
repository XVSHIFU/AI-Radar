import asyncio
import hashlib
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.admin_persistence import (
    InvalidAdminToken,
    LoginRateLimited,
    PostgresAdminSessionStore,
)

pytestmark = pytest.mark.postgres


async def _exercise_shared_state(database: Any) -> None:
    engine = create_async_engine(
        database.url.set(drivername="postgresql+asyncpg"), pool_pre_ping=True
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    first = PostgresAdminSessionStore(sessions)
    second = PostgresAdminSessionStore(sessions)
    try:
        token, created = await first.login("right-token", "right-token", "198.51.100.8")
        loaded = await second.get(token)
        assert loaded == created

        async with sessions() as session:
            stored = await session.execute(
                text("SELECT token_hash, csrf_token FROM admin_sessions")
            )
            token_hash, csrf_token = stored.one()
            assert token_hash == hashlib.sha256(token.encode()).hexdigest()
            assert token not in {token_hash, csrf_token}

        results = await asyncio.gather(
            *[
                (first if index % 2 else second).login("wrong-token", "right-token", "203.0.113.9")
                for index in range(6)
            ],
            return_exceptions=True,
        )
        assert sum(isinstance(result, InvalidAdminToken) for result in results) == 5
        assert sum(isinstance(result, LoginRateLimited) for result in results) == 1
        async with sessions() as session:
            client_hash = await session.scalar(
                text("SELECT client_hash FROM admin_login_failures WHERE failure_count = 5")
            )
            assert client_hash == hashlib.sha256(b"203.0.113.9").hexdigest()
            assert client_hash != "203.0.113.9"

        await second.logout(token)
        assert await first.get(token) is None
    finally:
        await engine.dispose()


def test_sessions_and_login_limits_are_shared_and_hashed(postgres_database: Any) -> None:
    asyncio.run(_exercise_shared_state(postgres_database))


async def _table_names(database: Any) -> set[str]:
    connection = await database.connect()
    try:
        rows = await connection.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        return {row["table_name"] for row in rows}
    finally:
        await connection.close()


def test_admin_durable_migration_round_trip(migration_database: Any) -> None:
    migration_database.upgrade("0010_admin_durable")
    tables = asyncio.run(_table_names(migration_database))
    assert {
        "admin_sessions",
        "admin_login_failures",
        "admin_audit_log",
    } <= tables
    migration_database.downgrade("0009_retrieval")
