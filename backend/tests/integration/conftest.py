import asyncio
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy import URL, make_url

from alembic import command
from radar.config import Settings, get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_PREFIX = "radar_test_"


class DatabaseHarness:
    def __init__(self, url: URL) -> None:
        database = url.database
        if database is None or not database.startswith(TEST_DATABASE_PREFIX):
            raise ValueError("integration database must use the radar_test_ prefix")
        self.url = url

    @property
    def rendered_url(self) -> str:
        return self.url.render_as_string(hide_password=False)

    async def connect(self) -> asyncpg.Connection:
        return await _connect(self.url)

    def upgrade(self, revision: str = "head") -> None:
        _run_alembic(self.rendered_url, command.upgrade, revision)

    def downgrade(self, revision: str) -> None:
        _run_alembic(self.rendered_url, command.downgrade, revision)


def _configured_url() -> URL:
    rendered = Settings().alembic_url()
    if rendered is None:
        pytest.skip("PostgreSQL is not configured")
    return make_url(rendered)


async def _connect(url: URL, *, database: str | None = None) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database=database or url.database,
    )


async def _create_database(server_url: URL) -> DatabaseHarness:
    name = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    connection = await _connect(server_url)
    try:
        await connection.execute(f'CREATE DATABASE "{name}"')
    finally:
        await connection.close()
    return DatabaseHarness(server_url.set(database=name))


async def _drop_database(server_url: URL, harness: DatabaseHarness) -> None:
    name = harness.url.database
    if name is None or not name.startswith(TEST_DATABASE_PREFIX):
        raise ValueError("refusing to drop a database outside the test prefix")
    connection = await _connect(server_url)
    try:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            name,
        )
        await connection.execute(f'DROP DATABASE "{name}"')
    finally:
        await connection.close()


@contextmanager
def _database_environment(url: str) -> Iterator[None]:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def _run_alembic(url: str, operation: object, revision: str) -> None:
    configuration = Config(str(BACKEND_ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    with _database_environment(url):
        operation(configuration, revision)  # type: ignore[operator]


def _database_fixture() -> Iterator[DatabaseHarness]:
    if os.environ.get("RADAR_RUN_POSTGRES_TESTS") != "1":
        pytest.skip("set RADAR_RUN_POSTGRES_TESTS=1 to run live PostgreSQL tests")
    server_url = _configured_url()
    if server_url.host not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("live PostgreSQL tests require an explicitly configured loopback server")
    harness = asyncio.run(_create_database(server_url))
    try:
        yield harness
    finally:
        asyncio.run(_drop_database(server_url, harness))


@pytest.fixture(scope="session")
def postgres_database() -> Iterator[DatabaseHarness]:
    for harness in _database_fixture():
        harness.upgrade()
        yield harness


@pytest.fixture(scope="session")
def migration_database() -> Iterator[DatabaseHarness]:
    yield from _database_fixture()
