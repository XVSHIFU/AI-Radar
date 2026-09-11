import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import BudgetReservationRow, IngestJobRow, IngestRunRow, SourceRow


class IdempotencyConflict(ValueError):
    pass


class SourceRejected(ValueError):
    pass


class BudgetUnavailable(ValueError):
    pass


class IngestRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def create_run(self, source_ids: list[UUID], key: str) -> tuple[IngestRunRow, bool]:
        unique_ids = sorted(set(source_ids), key=str)
        payload_hash = hashlib.sha256(
            json.dumps([str(item) for item in unique_ids]).encode()
        ).hexdigest()
        async with self.sessions() as session, session.begin():
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
                trigger_type="manual",
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
                        payload={"source_id": str(source_id)},
                    )
                    for source_id in unique_ids
                ]
            )
        return run, False

    async def runs(self) -> list[IngestRunRow]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(100)
                    )
                ).all()
            )

    async def claim(self, owner: str, lease_seconds: int = 60) -> IngestJobRow | None:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            await session.execute(
                update(IngestJobRow)
                .where(
                    IngestJobRow.state == "running",
                    IngestJobRow.lease_until < now,
                    IngestJobRow.attempts >= IngestJobRow.max_attempts,
                )
                .values(
                    state="failed",
                    lease_owner=None,
                    lease_until=None,
                    last_error="lease expired after final attempt",
                )
            )
            job = await session.scalar(
                select(IngestJobRow)
                .where(
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

    async def finish(
        self, job_id: UUID, owner: str, generation: int, success: bool, error: str | None = None
    ) -> bool:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
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
            if job.state == "retry_wait":
                job.not_before = now + timedelta(seconds=min(300, 2**generation))
            return True

    async def reserve_budget(
        self, scope: str, request_id: str, amount: Decimal, limit: Decimal | None
    ) -> BudgetReservationRow:
        if amount <= 0:
            raise BudgetUnavailable("reservation amount must be positive")
        if ":" not in scope:
            raise BudgetUnavailable("budget scope must include a bounded period")
        if limit is None or limit <= 0:
            raise BudgetUnavailable("budget is not configured")
        async with self.sessions() as session, session.begin():
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
