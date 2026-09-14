import asyncio
import os
import socket

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.config import get_settings
from radar.ingest.core import DocumentParseError
from radar.ingest.dns import configured_resolver
from radar.ingest.public_transport import PublicAsyncTransport
from radar.ingest.worker_service import LeaseLost, WorkerService
from radar.ingest_repository import IngestRepository


async def maintain_lease(
    repository: IngestRepository,
    job_id: object,
    owner: str,
    generation: int,
    lost: asyncio.Event,
) -> None:
    try:
        while True:
            await asyncio.sleep(20)
            if not await repository.heartbeat(job_id, owner, generation):  # type: ignore[arg-type]
                lost.set()
                return
    except asyncio.CancelledError:
        raise


async def run() -> None:
    settings = get_settings()
    url = settings.sqlalchemy_url()
    if settings.radar_data_mode != "postgres" or url is None:
        raise RuntimeError("worker requires configured PostgreSQL mode")
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = IngestRepository(sessions)
        owner = f"{socket.gethostname()}:{os.getpid()}"
        resolver = configured_resolver(settings.fetch_dns_mode)
        async with httpx.AsyncClient(
            transport=PublicAsyncTransport(resolver=resolver),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            service = WorkerService(sessions, client, resolver=resolver)
            while True:
                job = await repository.claim(owner)
                if job is None:
                    await asyncio.sleep(2)
                    continue
                lost = asyncio.Event()
                heartbeat = asyncio.create_task(
                    maintain_lease(repository, job.id, owner, job.lease_generation, lost)
                )
                try:
                    await service.process(job)
                    if lost.is_set():
                        raise LeaseLost("worker lease was lost during processing")
                    # WorkerService commits business rows and success atomically.
                except Exception as exc:
                    await repository.finish(
                        job.id,
                        owner,
                        job.lease_generation,
                        False,
                        str(exc),
                        parser_failure=isinstance(exc, DocumentParseError),
                    )
                finally:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat, return_exceptions=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
