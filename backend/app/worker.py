import asyncio
import os
import socket

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.config import get_settings
from radar.ingest.worker_service import WorkerService
from radar.ingest_repository import IngestRepository


async def run() -> None:
    settings = get_settings()
    url = settings.sqlalchemy_url()
    if settings.radar_data_mode != "postgres" or url is None:
        raise RuntimeError("worker requires configured PostgreSQL mode")
    engine = create_async_engine(url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = IngestRepository(sessions)
    owner = f"{socket.gethostname()}:{os.getpid()}"
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
        service = WorkerService(sessions, client)
        while True:
            job = await repository.claim(owner)
            if job is None:
                await asyncio.sleep(2)
                continue
            try:
                await service.process(job)
                await repository.finish(job.id, owner, job.lease_generation, True)
            except Exception as exc:
                await repository.finish(job.id, owner, job.lease_generation, False, str(exc))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
