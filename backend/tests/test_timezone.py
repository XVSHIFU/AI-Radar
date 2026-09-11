from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from radar.postgres_repository import PostgresRepository


def test_repository_constructs_with_iana_timezone_without_database() -> None:
    sessions = cast(async_sessionmaker[AsyncSession], None)
    repository = PostgresRepository(sessions, "review-secret-secret", "Asia/Shanghai")
    assert repository.timezone.key == "Asia/Shanghai"
