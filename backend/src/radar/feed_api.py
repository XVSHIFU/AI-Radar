"""Public article/event feed and article visibility controls."""

from datetime import date
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from .admin_auth import require_admin
from .feed_repository import FeedRepository
from .repository import InvalidCursor, RepositoryUnavailable
from .schemas import Category, Filters

router = APIRouter()


def _repository(request: Request) -> FeedRepository:
    repository = getattr(request.app.state, "feed_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "FEED_UNAVAILABLE", "message": "Feed requires PostgreSQL mode"},
        )
    return cast(FeedRepository, repository)


def _category(value: str | None) -> Category | None:
    if value is None or value == "unclassified":
        return None
    try:
        return Category(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_CATEGORY", "message": "unknown category"}
        ) from exc


def _filters(
    q: str | None,
    category: Category | None,
    date_from: date | None,
    date_to: date | None,
    min_importance: int | None,
) -> Filters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_DATE_RANGE", "message": "date_from must not be after date_to"},
        )
    return Filters(
        q=q, category=category, date_from=date_from, date_to=date_to, min_importance=min_importance
    )


@router.get("/api/v1/feed")
async def feed(
    request: Request,
    q: Annotated[str | None, Query(max_length=500)] = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_importance: Annotated[int | None, Query(ge=1, le=5)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = _filters(q, _category(category), date_from, date_to, min_importance)
    try:
        result = await _repository(request).list(filters, limit, cursor, category == "unclassified")
    except InvalidCursor as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_CURSOR", "message": str(exc)}
        ) from exc
    except RepositoryUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "RETRIEVAL_FAILED", "message": "Feed query failed"}
        ) from exc
    return {
        **result,
        "filters_applied": filters,
        "request_id": str(uuid4()),
        "data_mode": "postgres",
    }


@router.get("/api/v1/feed/stats")
async def feed_stats(request: Request) -> dict[str, Any]:
    return {**await _repository(request).stats(), "data_mode": "postgres"}


@router.get("/api/v1/feed/insights")
async def feed_insights(
    request: Request,
    date_from: date,
    date_to: date,
    q: Annotated[str | None, Query(max_length=500)] = None,
    category: str | None = None,
) -> dict[str, Any]:
    if (date_to - date_from).days > 365:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_DATE_RANGE", "message": "date range exceeds 366 days"},
        )
    filters = _filters(q, _category(category), date_from, date_to, None)
    return {
        **await _repository(request).insights(filters, category == "unclassified"),
        "date_from": date_from,
        "date_to": date_to,
        "timezone": _repository(request).timezone,
        "data_mode": "postgres",
    }


@router.get("/api/v1/feed/{item_id}")
async def feed_detail(item_id: UUID, request: Request) -> dict[str, Any]:
    item = await _repository(request).detail(item_id)
    if item is None:
        raise HTTPException(
            status_code=404, detail={"code": "ITEM_NOT_FOUND", "message": "Feed item was not found"}
        )
    if item["content_kind"] == "event":
        repository = request.app.state.repository
        item["evidence"] = [
            e.model_dump(mode="json") for e in await repository.evidence_for(item_id)
        ]
        item["articles"] = [
            a.model_dump(mode="json") for a in await repository.articles_for(item_id)
        ]
    return {**item, "data_mode": "postgres"}


@router.get("/api/v1/admin/articles", dependencies=[Depends(require_admin)])
async def admin_articles(
    request: Request,
    status: Literal["published", "hidden"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await _repository(request).admin_articles(status, limit)


class ArticleStatusChange(BaseModel):
    status: Literal["published", "hidden"]


@router.patch("/api/v1/admin/articles/{article_id}", dependencies=[Depends(require_admin)])
async def change_article_status(
    article_id: UUID, payload: ArticleStatusChange, request: Request
) -> dict[str, Any]:
    item = await _repository(request).set_status(article_id, payload.status)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTICLE_NOT_FOUND", "message": "Article was not found"},
        )
    return item
