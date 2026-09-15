from __future__ import annotations

import secrets
from hmac import compare_digest

from fastapi import HTTPException, Request

from .admin_persistence import AdminSessionStore

SESSION_COOKIE = "radar_admin_session"


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


async def require_admin(request: Request) -> None:
    expected = request.app.state.settings.admin_token
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer ") and expected:
        supplied = authorization.removeprefix("Bearer ")
        if compare_digest(supplied.encode(), expected.encode()):
            return
    store: AdminSessionStore = request.app.state.admin_sessions
    session = await store.get(request.cookies.get(SESSION_COOKIE))
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
