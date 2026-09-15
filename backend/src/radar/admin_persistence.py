from __future__ import annotations

import hashlib
import secrets
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from typing import Protocol

from sqlalchemy import DateTime, Index, Integer, String, delete, select
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base

SESSION_TTL = timedelta(hours=8)
LOGIN_WINDOW = timedelta(minutes=1)


class AdminSessionRow(Base):
    __tablename__ = "admin_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_admin_sessions_expires_at", "expires_at"),)


class AdminLoginFailureRow(Base):
    __tablename__ = "admin_login_failures"

    client_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_admin_login_failures_updated_at", "updated_at"),)


class AdminAuditRow(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(255))
    status_code: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    request_id: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_admin_audit_log_occurred_at_id", occurred_at.desc(), id.desc()),)


@dataclass(frozen=True)
class AdminSession:
    csrf_token: str
    expires_at: datetime


class LoginRateLimited(Exception):
    pass


class InvalidAdminToken(Exception):
    pass


class AdminSessionStore(Protocol):
    async def login(
        self, supplied: str, expected: str | None, client: str
    ) -> tuple[str, AdminSession]: ...

    async def get(self, token: str | None) -> AdminSession | None: ...

    async def logout(self, token: str | None) -> None: ...


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _valid_token(supplied: str, expected: str | None) -> bool:
    if expected is None:
        return False
    return compare_digest(supplied.encode(), expected.encode())


class MemoryAdminSessionStore:
    def __init__(self, *, max_sessions: int = 256, max_failures: int = 5) -> None:
        self._sessions: dict[str, AdminSession] = {}
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)
        self._max_sessions = max_sessions
        self._max_failures = max_failures

    async def login(
        self, supplied: str, expected: str | None, client: str
    ) -> tuple[str, AdminSession]:
        now = datetime.now(UTC)
        self._prune(now)
        failures = self._failures[_hash(client)]
        cutoff = now - LOGIN_WINDOW
        while failures and failures[0] < cutoff:
            failures.popleft()
        if len(failures) >= self._max_failures:
            raise LoginRateLimited
        if not _valid_token(supplied, expected):
            failures.append(now)
            raise InvalidAdminToken
        failures.clear()
        while len(self._sessions) >= self._max_sessions:
            oldest = min(self._sessions, key=lambda key: self._sessions[key].expires_at)
            self._sessions.pop(oldest, None)
        token = secrets.token_urlsafe(32)
        session = AdminSession(secrets.token_urlsafe(32), now + SESSION_TTL)
        self._sessions[_hash(token)] = session
        return token, session

    async def get(self, token: str | None) -> AdminSession | None:
        now = datetime.now(UTC)
        self._prune(now)
        return self._sessions.get(_hash(token)) if token else None

    async def logout(self, token: str | None) -> None:
        if token:
            self._sessions.pop(_hash(token), None)

    def _prune(self, now: datetime) -> None:
        expired = [key for key, value in self._sessions.items() if value.expires_at <= now]
        for key in expired:
            self._sessions.pop(key, None)


class PostgresAdminSessionStore:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, max_failures: int = 5
    ) -> None:
        self._sessions = sessions
        self._max_failures = max_failures

    async def login(
        self, supplied: str, expected: str | None, client: str
    ) -> tuple[str, AdminSession]:
        now = datetime.now(UTC)
        client_hash = _hash(client)
        valid = _valid_token(supplied, expected)
        token = secrets.token_urlsafe(32)
        value = AdminSession(secrets.token_urlsafe(32), now + SESSION_TTL)
        outcome: str
        async with self._sessions() as db, db.begin():
            expired = (
                select(AdminLoginFailureRow.client_hash)
                .where(AdminLoginFailureRow.updated_at < now - LOGIN_WINDOW)
                .order_by(AdminLoginFailureRow.updated_at)
                .limit(1000)
                .with_for_update(skip_locked=True)
            )
            await db.execute(
                delete(AdminLoginFailureRow).where(AdminLoginFailureRow.client_hash.in_(expired))
            )
            await db.execute(
                insert(AdminLoginFailureRow)
                .values(
                    client_hash=client_hash,
                    window_started_at=now,
                    failure_count=0,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=[AdminLoginFailureRow.client_hash])
            )
            failures = await db.scalar(
                select(AdminLoginFailureRow)
                .where(AdminLoginFailureRow.client_hash == client_hash)
                .with_for_update()
            )
            assert failures is not None
            if failures.window_started_at <= now - LOGIN_WINDOW:
                failures.window_started_at = now
                failures.failure_count = 0
            if failures.failure_count >= self._max_failures:
                outcome = "limited"
            elif not valid:
                failures.failure_count += 1
                failures.updated_at = now
                outcome = "invalid"
            else:
                # Keep this row through concurrent successful logins; deleting it can
                # race with another INSERT ... ON CONFLICT followed by SELECT FOR UPDATE.
                failures.failure_count = 0
                failures.window_started_at = now
                failures.updated_at = now
                await db.execute(delete(AdminSessionRow).where(AdminSessionRow.expires_at <= now))
                db.add(
                    AdminSessionRow(
                        token_hash=_hash(token),
                        csrf_token=value.csrf_token,
                        created_at=now,
                        expires_at=value.expires_at,
                    )
                )
                outcome = "accepted"
        if outcome == "limited":
            raise LoginRateLimited
        if outcome == "invalid":
            raise InvalidAdminToken
        return token, value

    async def get(self, token: str | None) -> AdminSession | None:
        if token is None:
            return None
        now = datetime.now(UTC)
        async with self._sessions() as db, db.begin():
            row = await db.get(AdminSessionRow, _hash(token))
            if row is None:
                return None
            if row.expires_at <= now:
                await db.delete(row)
                return None
            return AdminSession(row.csrf_token, row.expires_at)

    async def logout(self, token: str | None) -> None:
        if token is None:
            return
        async with self._sessions() as db, db.begin():
            await db.execute(
                delete(AdminSessionRow).where(AdminSessionRow.token_hash == _hash(token))
            )


async def append_admin_audit(
    sessions: async_sessionmaker[AsyncSession],
    *,
    action: str,
    target: str,
    status_code: int,
    request_id: str,
) -> None:
    async with sessions() as db, db.begin():
        db.add(
            AdminAuditRow(
                id=uuid.uuid4(),
                action=action,
                target=target,
                status_code=status_code,
                outcome="success" if 200 <= status_code < 400 else "failure",
                request_id=request_id,
                occurred_at=datetime.now(UTC),
            )
        )
