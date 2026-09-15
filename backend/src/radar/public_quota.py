"""Persistent public-question admission. Model calls remain outside database locks.

Reservations fail closed: a process crash leaves its maximum token charge recorded.
Only a verified settlement releases unused budget. No transcript or raw IP is stored.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base

WINDOW = timedelta(hours=48)
GLOBAL_ADMISSION_LOCK = 82534290116934
HEX_KEY = re.compile(r"[0-9a-f]{64}\Z")
REQUEST_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class PublicAskRow(Base):
    __tablename__ = "public_ask_requests"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64))
    client_request_id: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    ip_hash: Mapped[str] = mapped_column(String(64))
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    charged: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(16))
    input_charge: Mapped[int] = mapped_column(Integer)
    output_charge: Mapped[int] = mapped_column(Integer)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("owner_hash", "client_request_id", name="uq_public_ask_owner_request"),
        Index("ix_public_ask_ip_time", "ip_hash", "admitted_at"),
        Index("ix_public_ask_admitted_at", "admitted_at"),
    )


@dataclass(frozen=True)
class QuotaPolicy:
    questions: int = 20
    max_active: int = 2
    run_seconds: int = 90
    input_per_run: int = 24_000
    output_per_run: int = 4_800
    input_per_day: int = 200_000
    output_per_day: int = 32_000

    def __post_init__(self) -> None:
        for value in vars(self).values():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("quota limits must be positive integers")


@dataclass(frozen=True)
class QuotaSnapshot:
    remaining: int
    limit: int
    next_available_at: datetime | None


@dataclass(frozen=True)
class PublicReservation:
    id: UUID
    deadline: datetime
    quota: QuotaSnapshot


class PublicAdmissionError(Exception):
    def __init__(
        self, code: str, status: int, *, retry_after: int = 0, quota: QuotaSnapshot | None = None
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = max(0, retry_after)
        self.quota = quota


def _key(value: str) -> None:
    if not HEX_KEY.fullmatch(value):
        raise ValueError("expected a server-derived private key")


class PostgresPublicQuota:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], policy: QuotaPolicy | None = None
    ) -> None:
        self.sessions = sessions
        self.policy = policy or QuotaPolicy()

    async def _now(self, session: AsyncSession) -> datetime:
        # Read after acquiring admission locks so queue time does not stale the window.
        value = await session.scalar(select(func.clock_timestamp()))
        assert isinstance(value, datetime)
        return value

    async def _snapshot(self, session: AsyncSession, ip_hash: str, now: datetime) -> QuotaSnapshot:
        count, earliest = (
            await session.execute(
                select(func.count(), func.min(PublicAskRow.admitted_at)).where(
                    PublicAskRow.ip_hash == ip_hash,
                    PublicAskRow.charged.is_(True),
                    PublicAskRow.admitted_at > now - WINDOW,
                )
            )
        ).one()
        remaining = max(0, self.policy.questions - count)
        return QuotaSnapshot(
            remaining, self.policy.questions, earliest + WINDOW if not remaining else None
        )

    async def snapshot(self, ip_hash: str) -> QuotaSnapshot:
        _key(ip_hash)
        async with self.sessions() as session:
            return await self._snapshot(session, ip_hash, await self._now(session))

    async def reserve(
        self, owner_hash: str, ip_hash: str, request_key: str, payload_hash: str
    ) -> PublicReservation:
        for key in (owner_hash, ip_hash, payload_hash):
            _key(key)
        if not REQUEST_KEY.fullmatch(request_key):
            raise PublicAdmissionError("INVALID_CLIENT_REQUEST_ID", 422)
        async with self.sessions() as session, session.begin():
            # Always global then IP: no per-session lock bypass and no inverted lock order.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": GLOBAL_ADMISSION_LOCK}
            )
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": int.from_bytes(bytes.fromhex(ip_hash[:16]), "big", signed=True)},
            )
            now = await self._now(session)
            old = await session.scalar(
                select(PublicAskRow).where(
                    PublicAskRow.owner_hash == owner_hash,
                    PublicAskRow.client_request_id == request_key,
                )
            )
            if old is not None:
                raise PublicAdmissionError(
                    "IDEMPOTENCY_REPLAY"
                    if old.payload_hash == payload_hash
                    else "IDEMPOTENCY_KEY_CONFLICT",
                    409,
                )
            quota = await self._snapshot(session, ip_hash, now)
            if not quota.remaining:
                assert quota.next_available_at is not None
                raise PublicAdmissionError(
                    "ASK_QUOTA_EXCEEDED",
                    429,
                    retry_after=math.ceil((quota.next_available_at - now).total_seconds()),
                    quota=quota,
                )
            active = list(
                (
                    await session.scalars(
                        select(PublicAskRow.active_until).where(
                            PublicAskRow.status == "reserved", PublicAskRow.active_until > now
                        )
                    )
                ).all()
            )
            if len(active) >= self.policy.max_active:
                raise PublicAdmissionError(
                    "ASK_BUSY", 429, retry_after=math.ceil((min(active) - now).total_seconds())
                )
            # UTC accounting day. Unknown work spanning midnight remains charged until settled.
            day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            input_sum, output_sum = (
                await session.execute(
                    select(
                        func.coalesce(func.sum(PublicAskRow.input_charge), 0),
                        func.coalesce(func.sum(PublicAskRow.output_charge), 0),
                    ).where(
                        (PublicAskRow.admitted_at >= day)
                        | ((PublicAskRow.status == "reserved") & (PublicAskRow.active_until > now))
                    )
                )
            ).one()
            if (
                input_sum + self.policy.input_per_run > self.policy.input_per_day
                or output_sum + self.policy.output_per_run > self.policy.output_per_day
            ):
                raise PublicAdmissionError(
                    "ASK_DAILY_BUDGET_EXCEEDED",
                    429,
                    retry_after=math.ceil((day + timedelta(days=1) - now).total_seconds()),
                )
            row = PublicAskRow(
                id=uuid4(),
                owner_hash=owner_hash,
                ip_hash=ip_hash,
                client_request_id=request_key,
                payload_hash=payload_hash,
                admitted_at=now,
                active_until=now + timedelta(seconds=self.policy.run_seconds),
                charged=True,
                status="reserved",
                input_charge=self.policy.input_per_run,
                output_charge=self.policy.output_per_run,
            )
            session.add(row)
            await session.flush()
            return PublicReservation(
                row.id, row.active_until, await self._snapshot(session, ip_hash, now)
            )

    async def settle(
        self,
        reservation_id: UUID,
        owner_hash: str,
        *,
        started: bool,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """Trusted controller only. None retains reservation; known zero is explicitly zero.

        started=False releases question and token charges after a pre-execution rejection.
        The terminal idempotency record is kept, so retries cannot double-execute that key.
        """
        _key(owner_hash)
        for value in (input_tokens, output_tokens):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError("usage must be a nonnegative integer or unknown")
        async with self.sessions() as session, session.begin():
            row = await session.scalar(
                select(PublicAskRow)
                .where(PublicAskRow.id == reservation_id, PublicAskRow.owner_hash == owner_hash)
                .with_for_update()
            )
            if row is None:
                raise PublicAdmissionError("RUN_NOT_FOUND", 404)
            if row.status != "reserved":
                return
            now = await self._now(session)
            row.status = "finished" if started else "rejected"
            row.active_until = now
            row.settled_at = now
            row.charged = started
            if not started:
                row.input_charge = row.output_charge = 0
            else:
                if input_tokens is not None:
                    row.input_charge = input_tokens
                if output_tokens is not None:
                    row.output_charge = output_tokens
