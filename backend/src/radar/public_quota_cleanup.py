"""Trusted maintenance only; never exposed as a model or public API tool."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import Settings
from .public_identity import SESSION_LIFETIME
from .public_quota import WINDOW, PublicAskRow

IDEMPOTENCY_RETENTION = SESSION_LIFETIME + timedelta(days=1)


@dataclass(frozen=True)
class CleanupResult:
    forgotten_ips: int
    deleted_requests: int


async def clean_public_quota(
    sessions: async_sessionmaker[AsyncSession], *, batch_size: int = 1000
) -> CleanupResult:
    if type(batch_size) is not int or not 1 <= batch_size <= 5000:
        raise ValueError("batch size must be between 1 and 5000")
    async with sessions() as session, session.begin():
        await session.execute(text("SET LOCAL statement_timeout = '10s'"))
        await session.execute(text("SET LOCAL lock_timeout = '1s'"))
        now = await session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        # Skip running/locked rows rather than waiting on an answer settlement.
        expired = list(
            (
                await session.scalars(
                    select(PublicAskRow.id)
                    .where(
                        PublicAskRow.admitted_at <= now - IDEMPOTENCY_RETENTION,
                        PublicAskRow.active_until <= now,
                    )
                    .order_by(PublicAskRow.admitted_at, PublicAskRow.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if expired:
            # Research-call links cascade; the independent llm_calls usage stays intact.
            await session.execute(delete(PublicAskRow).where(PublicAskRow.id.in_(expired)))
        forgotten = list(
            (
                await session.scalars(
                    select(PublicAskRow.id)
                    .where(
                        PublicAskRow.admitted_at <= now - WINDOW,
                        PublicAskRow.active_until <= now,
                        PublicAskRow.ip_hash.is_not(None),
                    )
                    .order_by(PublicAskRow.admitted_at, PublicAskRow.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if forgotten:
            await session.execute(
                update(PublicAskRow).where(PublicAskRow.id.in_(forgotten)).values(ip_hash=None)
            )
        return CleanupResult(len(forgotten), len(expired))


async def run_once() -> CleanupResult:
    settings = Settings()
    url = settings.sqlalchemy_url()
    if not url or settings.radar_data_mode != "postgres":
        raise ValueError("PostgreSQL maintenance configuration is required")
    engine = create_async_engine(url)
    try:
        return await clean_public_quota(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def main() -> None:
    try:
        result = asyncio.run(run_once())
    except Exception:
        # DB exception text can contain connection information. Only a safe failure code
        # belongs in service logs; reservations remain intact after transaction rollback.
        logging.error("public_quota_cleanup_failed")
        raise SystemExit(1) from None
    print(json.dumps(asdict(result)))


if __name__ == "__main__":
    main()
