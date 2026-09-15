"""HTTP ownership and lifecycle for metered public answers, outside the model runtime."""

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from .models import LlmCallRow
from .public_identity import SESSION_LIFETIME, PublicIdentity
from .public_quota import PostgresPublicQuota, PublicAdmissionError, PublicReservation
from .qa_service import payload_hash
from .schemas import AskRequest, QueryPlan

router = APIRouter()
COOKIE = "radar_assistant_session"
logger = logging.getLogger(__name__)
MESSAGES = {
    "ASK_QUOTA_EXCEEDED": "该 IP 在过去 48 小时内已发送 20 次问题，请在额度恢复后再试。",
    "ASK_BUSY": "助手正在处理其他问题，请稍后再试。",
    "ASK_DAILY_BUDGET_EXCEEDED": "体验预算已用完，请在额度恢复后再试。",
    "IDEMPOTENCY_REPLAY": "该问题已提交，请查看原会话；未重复扣除额度。",
    "IDEMPOTENCY_KEY_CONFLICT": "请求标识已用于其他问题，请重新发送。",
    "INVALID_CLIENT_REQUEST_ID": "问题请求标识无效。",
}


def unavailable() -> HTTPException:
    return HTTPException(
        503,
        detail={
            "code": "ASSISTANT_QUOTA_UNAVAILABLE",
            "message": "助手额度服务暂不可用，请稍后再试。",
            "retryable": True,
        },
    )


def services(request: Request) -> tuple[PublicIdentity, PostgresPublicQuota]:
    identity = getattr(request.app.state, "public_identity", None)
    quota = getattr(request.app.state, "public_quota", None)
    if identity is None or quota is None:
        raise unavailable()
    return identity, quota


def private_ip(request: Request, identity: PublicIdentity) -> str:
    # Uvicorn may resolve a trusted loopback proxy. Never parse arbitrary X-Forwarded-For here.
    if request.client is None:
        raise unavailable()
    try:
        return identity.ip_key(request.client.host)
    except ValueError as exc:
        raise unavailable() from exc


@router.get("/api/v1/assistant/session")
async def assistant_session(request: Request, response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    if request.app.state.settings.radar_data_mode == "fixture":
        return {"quota": None, "data_mode": "fixture"}
    identity, quota = services(request)
    snapshot = await quota.snapshot(private_ip(request, identity))
    if identity.subject(request.cookies.get(COOKIE)) is None:
        response.set_cookie(
            COOKIE,
            identity.issue(),
            max_age=int(SESSION_LIFETIME.total_seconds()),
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            path="/api/v1",
        )
    return {"quota": {**asdict(snapshot), "window_hours": 48}, "data_mode": "postgres"}


@dataclass
class PublicRun:
    quota: PostgresPublicQuota
    owner: str
    reservation: PublicReservation
    payload: AskRequest

    @property
    def seconds_left(self) -> float:
        return max(0, (self.reservation.deadline - datetime.now(UTC)).total_seconds())

    async def finish(self, *, completed: bool) -> None:
        async def settle() -> None:
            async with self.quota.sessions() as session:
                row = await session.scalar(
                    select(LlmCallRow).where(
                        LlmCallRow.purpose == "answer_generation",
                        LlmCallRow.logical_request_id == f"answer:{self.payload.client_request_id}",
                    )
                )
                started = completed or row is not None
                await self.quota.settle(
                    self.reservation.id,
                    self.owner,
                    started=started,
                    input_tokens=row.prompt_tokens if row else 0,
                    output_tokens=row.completion_tokens if row else 0,
                )

        try:
            # Disconnects must not cancel accounting. Failed accounting retains the reservation.
            await asyncio.shield(settle())
        except Exception:
            logger.exception(
                "public answer settlement failed", extra={"run": str(self.reservation.id)}
            )


async def begin_public_run(
    request: Request, payload: AskRequest, plan: QueryPlan
) -> PublicRun | None:
    if request.app.state.settings.radar_data_mode == "fixture":
        return None
    identity, quota = services(request)
    owner = identity.subject(request.cookies.get(COOKIE))
    if owner is None:
        raise HTTPException(
            428,
            detail={
                "code": "ASSISTANT_SESSION_REQUIRED",
                "message": "会话已过期，请刷新后再试。",
                "retryable": False,
            },
        )
    try:
        reservation = await quota.reserve(
            owner,
            private_ip(request, identity),
            payload.client_request_id,
            identity.digest("payload", payload_hash(payload, plan)),
        )
    except PublicAdmissionError as exc:
        details: dict[str, object] = {"retry_after_seconds": exc.retry_after}
        if exc.quota:
            details["quota"] = {
                **asdict(exc.quota),
                "next_available_at": exc.quota.next_available_at.isoformat()
                if exc.quota.next_available_at
                else None,
                "window_hours": 48,
            }
        raise HTTPException(
            exc.status,
            detail={
                "code": exc.code,
                "message": MESSAGES.get(exc.code, "暂时无法提交问题。"),
                "retryable": False,
                "details": details,
            },
            headers={"Retry-After": str(exc.retry_after), "Cache-Control": "no-store"},
        ) from exc
    # Legacy paid-call idempotency is global. Use a server ID bound to this anonymous owner.
    owned_payload = payload.model_copy(update={"client_request_id": f"pub-{reservation.id.hex}"})
    return PublicRun(quota, owner, reservation, owned_payload)
