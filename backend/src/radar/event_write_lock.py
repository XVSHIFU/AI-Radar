"""Serialize short publication/curation transactions, never model or network calls.

The current single-team deployment has few writers. A shared transaction lock keeps
dynamic merge membership and event/entity row locks in one consistent order. Reads
remain concurrent; a future multi-writer deployment can partition this lock only
after adding a graph-aware lock protocol and concurrency acceptance tests.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_event_writes(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('radar:event-write:v1', 0))")
    )
