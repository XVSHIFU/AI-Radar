import asyncio
from datetime import UTC, datetime
from uuid import UUID

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.config import get_settings
from radar.ingest_repository import IngestRepository
from radar.models import SourceRow


async def enqueue() -> None:
    settings = get_settings()
    url = settings.sqlalchemy_url()
    if settings.radar_data_mode != "postgres" or url is None:
        raise RuntimeError("scheduler requires configured PostgreSQL mode")
    engine = create_async_engine(url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        source_ids = list(
            (await session.scalars(select(SourceRow.id).where(SourceRow.enabled.is_(True)))).all()
        )
    if source_ids:
        period = datetime.now(UTC).strftime("%Y-%m-%dT%H")
        await IngestRepository(sessions).create_run(
            [UUID(str(item)) for item in source_ids], f"schedule:{period}"
        )
    await engine.dispose()


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: asyncio.run(enqueue()), "interval", minutes=60, max_instances=1, coalesce=True
    )
    scheduler.start()


if __name__ == "__main__":
    main()
