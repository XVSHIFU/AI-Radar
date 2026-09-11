import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from .models import BudgetReservationRow, IngestJobRow, IngestRunRow, SourceRow
from .repository import RepositoryUnavailable


class IdempotencyConflict(ValueError):
    pass


class SourceRejected(ValueError):
    pass


class BudgetUnavailable(ValueError):
    pass


class IngestRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    @asynccontextmanager
    async def _database_boundary(self) -> AsyncIterator[None]:
        try:
            yield
        except (OSError, SQLAlchemyError) as exc:
            raise RepositoryUnavailable("Ingest database operation failed") from exc

    async def create_run(
        self, source_ids: list[UUID], key: str, trigger_type: str = "manual"
    ) -> tuple[IngestRunRow, bool]:
        unique_ids = sorted(set(source_ids), key=str)
        payload_hash = hashlib.sha256(
            json.dumps([str(item) for item in unique_ids]).encode()
        ).hexdigest()
        async with self._database_boundary(), self.sessions() as session, session.begin():
            await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
            existing = await session.scalar(
                select(IngestRunRow).where(IngestRunRow.idempotency_key == key)
            )
            if existing:
                if existing.payload_hash != payload_hash:
                    raise IdempotencyConflict("idempotency key is bound to another payload")
                return existing, True
            configured = set(
                (
                    await session.scalars(
                        select(SourceRow.id).where(
                            SourceRow.id.in_(unique_ids), SourceRow.enabled.is_(True)
                        )
                    )
                ).all()
            )
            if configured != set(unique_ids):
                raise SourceRejected("all source_ids must reference enabled configured sources")
            run = IngestRunRow(
                id=uuid4(),
                idempotency_key=key,
                payload_hash=payload_hash,
                trigger_type=trigger_type,
                status="queued",
            )
            session.add(run)
            await session.flush()
            session.add_all(
                [
                    IngestJobRow(
                        id=uuid4(),
                        run_id=run.id,
                        source_id=source_id,
                        job_key=f"source:{run.id}:{source_id}",
                        stage="feed_discovery",
                        payload={"source_id": str(source_id)},
                    )
                    for source_id in unique_ids
                ]
            )
        return run, False

    async def runs(self) -> list[IngestRunRow]:
        async with self._database_boundary(), self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(100)
                    )
                ).all()
            )

    async def claim(self, owner: str, lease_seconds: int = 60) -> IngestJobRow | None:
        now = datetime.now(UTC)
        async with self._database_boundary(), self.sessions() as session, session.begin():
            expired_jobs = list(
                (
                    await session.scalars(
                        select(IngestJobRow)
                        .where(
                            IngestJobRow.state == "running",
                            IngestJobRow.lease_until < now,
                            IngestJobRow.attempts >= IngestJobRow.max_attempts,
                        )
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            expired_job_ids = [item.id for item in expired_jobs]
            if expired_job_ids:
                await session.execute(
                    update(IngestJobRow)
                    .where(IngestJobRow.id.in_(expired_job_ids))
                    .values(
                        state="failed",
                        lease_owner=None,
                        lease_until=None,
                        last_error="lease expired after final attempt",
                    )
                )
            for expired_run_id in {item.run_id for item in expired_jobs}:
                await self._summarize_run(session, expired_run_id, now)
            unfinished_discovery = aliased(IngestJobRow)
            article_is_unblocked = ~exists(
                select(1).where(
                    unfinished_discovery.run_id == IngestJobRow.run_id,
                    unfinished_discovery.stage == "feed_discovery",
                    unfinished_discovery.state.in_(("queued", "retry_wait", "running")),
                )
            )
            job = await session.scalar(
                select(IngestJobRow)
                .where(
                    or_(IngestJobRow.stage != "article_fetch", article_is_unblocked),
                    IngestJobRow.attempts < IngestJobRow.max_attempts,
                    IngestJobRow.not_before <= now,
                    or_(
                        IngestJobRow.state.in_(("queued", "retry_wait")),
                        and_(IngestJobRow.state == "running", IngestJobRow.lease_until < now),
                    ),
                )
                .order_by(IngestJobRow.not_before, IngestJobRow.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not job:
                return None
            job.state = "running"
            job.lease_owner = owner
            job.lease_generation += 1
            job.lease_until = now + timedelta(seconds=lease_seconds)
            job.attempts += 1
            await session.flush()
            session.expunge(job)
            return job

    async def heartbeat(
        self, job_id: UUID, owner: str, generation: int, lease_seconds: int = 60
    ) -> bool:
        now = datetime.now(UTC)
        async with self._database_boundary(), self.sessions() as session, session.begin():
            result = await session.execute(
                update(IngestJobRow)
                .where(
                    IngestJobRow.id == job_id,
                    IngestJobRow.lease_owner == owner,
                    IngestJobRow.lease_generation == generation,
                    IngestJobRow.state == "running",
                    IngestJobRow.lease_until >= now,
                )
                .values(lease_until=now + timedelta(seconds=lease_seconds))
            )
            return bool(cast(CursorResult[Any], result).rowcount)

    async def finish(
        self,
        job_id: UUID,
        owner: str,
        generation: int,
        success: bool,
        error: str | None = None,
        *,
        parser_failure: bool = False,
    ) -> bool:
        now = datetime.now(UTC)
        async with self._database_boundary(), self.sessions() as session, session.begin():
            job = await session.scalar(
                select(IngestJobRow)
                .where(
                    IngestJobRow.id == job_id,
                    IngestJobRow.lease_owner == owner,
                    IngestJobRow.lease_generation == generation,
                    IngestJobRow.state == "running",
                    IngestJobRow.lease_until >= now,
                )
                .with_for_update()
            )
            if job is None:
                return False
            job.state = (
                "succeeded"
                if success
                else ("failed" if job.attempts >= job.max_attempts else "retry_wait")
            )
            job.lease_owner = None
            job.lease_until = None
            job.last_error = error
            if not success and job.stage == "feed_discovery":
                source = await session.scalar(
                    select(SourceRow).where(SourceRow.id == job.source_id).with_for_update()
                )
                if source is not None:
                    source.last_checked_at = now
                    source.consecutive_failures += 1
                    source.health = "unhealthy" if source.consecutive_failures >= 3 else "degraded"
            if not success and parser_failure:
                await session.execute(
                    update(IngestRunRow)
                    .where(IngestRunRow.id == job.run_id)
                    .values(parser_failures=IngestRunRow.parser_failures + 1)
                )
            if job.state == "retry_wait":
                job.not_before = now + timedelta(seconds=min(300, 2**generation))
            await session.flush()
            await self._summarize_run(session, job.run_id, now)
            return True

    async def _summarize_run(self, session: AsyncSession, run_id: UUID, now: datetime) -> None:
        run = await session.scalar(
            select(IngestRunRow).where(IngestRunRow.id == run_id).with_for_update()
        )
        if run is None:
            return
        state_counts = (
            await session.execute(
                select(IngestJobRow.state, func.count())
                .where(IngestJobRow.run_id == run_id)
                .group_by(IngestJobRow.state)
            )
        ).all()
        counts: dict[str, int] = {row[0]: row[1] for row in state_counts}
        if sum(counts.get(state, 0) for state in ("queued", "retry_wait", "running")):
            run.status = "running"
            return
        failed = counts.get("failed", 0)
        succeeded = counts.get("succeeded", 0)
        run.failed_jobs = failed
        run.status = "partial" if failed and succeeded else ("failed" if failed else "success")
        run.finished_at = now
        if failed:
            errors = list(
                (
                    await session.scalars(
                        select(IngestJobRow.last_error)
                        .where(
                            IngestJobRow.run_id == run_id,
                            IngestJobRow.state == "failed",
                            IngestJobRow.last_error.is_not(None),
                        )
                        .order_by(IngestJobRow.id)
                        .limit(10)
                    )
                ).all()
            )
            run.error_summary = "; ".join(error for error in errors if error)

    async def reserve_budget(
        self, scope: str, request_id: str, amount: Decimal, limit: Decimal | None
    ) -> BudgetReservationRow:
        if amount <= 0:
            raise BudgetUnavailable("reservation amount must be positive")
        if ":" not in scope:
            raise BudgetUnavailable("budget scope must include a bounded period")
        if limit is None or limit <= 0:
            raise BudgetUnavailable("budget is not configured")
        async with self._database_boundary(), self.sessions() as session, session.begin():
            await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(scope))))
            existing = await session.scalar(
                select(BudgetReservationRow).where(
                    BudgetReservationRow.logical_request_id == request_id
                )
            )
            if existing is not None:
                if existing.scope != scope or existing.amount != amount:
                    raise BudgetUnavailable("logical request is bound to another reservation")
                return existing
            spent = (
                await session.scalar(
                    select(func.coalesce(func.sum(BudgetReservationRow.amount), 0)).where(
                        BudgetReservationRow.scope == scope,
                        BudgetReservationRow.state.in_(("reserved", "settled", "unknown")),
                    )
                )
            ) or Decimal("0")
            if Decimal(spent) + amount > limit:
                raise BudgetUnavailable("budget limit would be exceeded")
            reservation = BudgetReservationRow(
                id=uuid4(),
                scope=scope,
                logical_request_id=request_id,
                amount=amount,
                state="reserved",
            )
            session.add(reservation)
        return reservation
