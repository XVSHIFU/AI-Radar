from __future__ import annotations

import secrets
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest

from fastapi import HTTPException, Request

SESSION_COOKIE = "radar_admin_session"
SESSION_TTL = timedelta(hours=8)


@dataclass(frozen=True)
class AdminSession:
    csrf_token: str
    expires_at: datetime


def admin_error(code: str, message: str, status: int) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": message,
            "retryable": False,
            "request_id": secrets.token_hex(16),
        },
    )


class AdminSessionStore:
    def __init__(
        self, *, max_sessions: int = 256, max_failures: int = 5, max_clients: int = 1024
    ) -> None:
        self._sessions: dict[str, AdminSession] = {}
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)
        self._max_sessions = max_sessions
        self._max_failures = max_failures
        self._max_clients = max_clients

    def login(self, supplied: str, expected: str | None, client: str) -> tuple[str, AdminSession]:
        now = datetime.now(UTC)
        self._prune(now)
        while len(self._failures) >= self._max_clients and client not in self._failures:
            self._failures.pop(next(iter(self._failures)))
        failures = self._failures[client]
        cutoff = now - timedelta(minutes=1)
        while failures and failures[0] < cutoff:
            failures.popleft()
        if len(failures) >= self._max_failures:
            raise admin_error("LOGIN_RATE_LIMITED", "Too many login attempts", 429)
        if not expected or not compare_digest(supplied.encode(), expected.encode()):
            failures.append(now)
            raise admin_error("UNAUTHORIZED", "Administrator token is invalid", 401)
        failures.clear()
        self._prune(now)
        while len(self._sessions) >= self._max_sessions:
            oldest = min(self._sessions, key=lambda key: self._sessions[key].expires_at)
            self._sessions.pop(oldest, None)
        token = secrets.token_urlsafe(32)
        session = AdminSession(secrets.token_urlsafe(32), now + SESSION_TTL)
        self._sessions[token] = session
        return token, session

    def get(self, token: str | None) -> AdminSession | None:
        now = datetime.now(UTC)
        self._prune(now)
        if token is None:
            return None
        return self._sessions.get(token)

    def logout(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)

    def _prune(self, now: datetime) -> None:
        expired = [key for key, value in self._sessions.items() if value.expires_at <= now]
        for key in expired:
            self._sessions.pop(key, None)


def require_admin(request: Request) -> None:
    expected = request.app.state.settings.admin_token
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer ") and expected:
        supplied = authorization.removeprefix("Bearer ")
        if compare_digest(supplied.encode(), expected.encode()):
            return
    store: AdminSessionStore = request.app.state.admin_sessions
    cookie = request.cookies.get(SESSION_COOKIE)
    session = store.get(cookie)
    if session is None:
        if not expected:
            raise admin_error(
                "MANAGEMENT_UNAVAILABLE", "Administrator credentials are not configured", 503
            )
        raise admin_error("UNAUTHORIZED", "Valid administrator credentials are required", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("x-csrf-token")
        if csrf is None or not compare_digest(csrf.encode(), session.csrf_token.encode()):
            raise admin_error("CSRF_INVALID", "A valid CSRF token is required", 403)
