from __future__ import annotations

from datetime import date
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .admin_auth import admin_error, require_admin
from .date_quality import DateCorrectionRejected, DateQualityService
from .event_merge_service import EventMergeService, MergeRejected

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])


class EventMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_event_id: UUID
    target_event_id: UUID
    reason: str = Field(min_length=3, max_length=2000)
    evidence: dict[str, object]

    @field_validator("evidence")
    @classmethod
    def require_review_evidence(cls, value: dict[str, object]) -> dict[str, object]:
        if not value:
            raise ValueError("merge evidence must not be empty")
        return value


class EventDateCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: UUID
    event_date: date


def _sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    sessions = cast(async_sessionmaker[AsyncSession] | None, request.app.state.sessions)
    if sessions is None:
        raise admin_error("DATABASE_UNAVAILABLE", "PostgreSQL is not configured", 503)
    return sessions


def _operator(request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    return f"admin:{client}"


@router.post("/event-merges", status_code=201)
async def merge_events(payload: EventMergeRequest, request: Request) -> dict[str, object]:
    try:
        log_id = await EventMergeService(_sessions(request)).merge(
            payload.source_event_id,
            payload.target_event_id,
            reason=payload.reason,
            evidence=payload.evidence,
            operator=_operator(request),
        )
    except MergeRejected as exc:
        raise admin_error("EVENT_MERGE_REJECTED", str(exc), 409) from exc
    return {"merge_id": str(log_id), "status": "merged"}


@router.post("/event-merges/{merge_id}/revert")
async def unmerge_events(merge_id: UUID, request: Request) -> dict[str, object]:
    try:
        await EventMergeService(_sessions(request)).unmerge(
            merge_id, operator=_operator(request)
        )
    except MergeRejected as exc:
        raise admin_error("EVENT_UNMERGE_REJECTED", str(exc), 409) from exc
    return {"merge_id": str(merge_id), "status": "reverted"}


@router.get("/event-date-review")
async def review_event_dates(
    request: Request, limit: Annotated[int, Query(ge=1, le=5000)] = 1000
) -> dict[str, object]:
    rows = await DateQualityService(_sessions(request)).audit(limit=limit)
    return {
        "dry_run": True,
        "items": [
            {
                "event_id": str(row.event_id),
                "current_date": row.current_date,
                "status": row.status,
                "candidates": [
                    {
                        "date": candidate,
                        "evidence_id": str(evidence_id),
                        "paragraph_id": paragraph_id,
                    }
                    for candidate, evidence_id, paragraph_id in row.candidates
                ],
            }
            for row in rows
        ],
    }


@router.post("/event-date-review/{event_id}")
async def correct_event_date(
    event_id: UUID, payload: EventDateCorrectionRequest, request: Request
) -> dict[str, object]:
    try:
        audit_id = await DateQualityService(_sessions(request)).apply(
            event_id,
            payload.evidence_id,
            payload.event_date,
            operator=_operator(request),
        )
    except DateCorrectionRejected as exc:
        raise admin_error("EVENT_DATE_CORRECTION_REJECTED", str(exc), 409) from exc
    return {"audit_id": str(audit_id), "status": "corrected"}
