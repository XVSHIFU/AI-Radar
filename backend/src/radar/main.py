from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import get_settings
from .fixture_repository import FixtureRepository
from .ingest_repository import IdempotencyConflict, IngestRepository, SourceRejected
from .postgres_repository import PostgresRepository
from .repository import EventRepository, EvidenceInvalid, InvalidCursor, RepositoryUnavailable
from .schemas import (
    AskRequest,
    Category,
    EventDetail,
    EventPage,
    EvidencePage,
    Filters,
    IngestRun,
    IngestRunCreated,
    IngestRunRequest,
)


def api_error(code: str, message: str, status: int, retryable: bool = False) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": message,
            "retryable": retryable,
            "request_id": str(uuid4()),
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.repository = None
    app.state.engine = None
    app.state.ingest_repository = None
    if settings.radar_data_mode == "fixture":
        path = Path(__file__).resolve().parents[3] / "contracts" / "prototype-events.json"
        app.state.repository = FixtureRepository(path, settings.cursor_secret)
    elif (url := settings.sqlalchemy_url()) is not None:
        engine = create_async_engine(url, pool_pre_ping=True)
        app.state.engine = engine
        app.state.ingest_repository = IngestRepository(
            async_sessionmaker(engine, expire_on_commit=False)
        )
        app.state.repository = PostgresRepository(
            async_sessionmaker(engine, expire_on_commit=False),
            settings.cursor_secret,
            settings.business_timezone,
        )
    yield
    if app.state.engine is not None:
        await app.state.engine.dispose()


app = FastAPI(title="AI Radar API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def handle_http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "retryable": False,
            "request_id": str(uuid4()),
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "retryable": False,
            "request_id": str(uuid4()),
            "details": {"errors": details},
        },
    )


@app.exception_handler(EvidenceInvalid)
async def handle_evidence_error(_request: Request, _exc: EvidenceInvalid) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "EVIDENCE_INVALID",
            "message": "Evidence cannot be located in its frozen article version",
            "retryable": False,
            "request_id": str(uuid4()),
        },
    )


@app.exception_handler(RepositoryUnavailable)
async def handle_repository_error(_request: Request, _exc: RepositoryUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "code": "RETRIEVAL_FAILED",
            "message": "Database retrieval failed",
            "retryable": True,
            "request_id": str(uuid4()),
        },
    )


def get_repository(request: Request) -> EventRepository:
    repository = cast(EventRepository | None, request.app.state.repository)
    if repository is None:
        raise api_error("DATABASE_UNAVAILABLE", "PostgreSQL is not configured", 503, True)
    return repository


def data_mode(request: Request) -> str:
    return cast(str, request.app.state.settings.radar_data_mode)


@app.get("/health")
@app.get("/health/live")
async def health(request: Request) -> dict[str, object]:
    configured = request.app.state.repository is not None
    return {
        "status": "live",
        "data_mode": data_mode(request),
        "database_configured": configured,
    }


@app.get("/health/ready")
async def ready(
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> dict[str, object]:
    if data_mode(request) == "fixture":
        return {
            "status": "fixture_ready",
            "data_mode": "fixture",
            "synthetic": True,
            "postgres_ready": False,
        }
    if not await repository.ready():
        raise api_error(
            "DATABASE_NOT_READY",
            "PostgreSQL migration or vector extension is not ready",
            503,
            True,
        )
    return {
        "status": "ready",
        "data_mode": "postgres",
        "synthetic": False,
        "postgres_ready": True,
    }


@app.get("/api/v1/events", response_model=EventPage)
async def list_events(
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
    q: str | None = None,
    category: Category | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_importance: Annotated[int | None, Query(ge=1, le=5)] = None,
    entity_ids: Annotated[list[UUID] | None, Query()] = None,
    entity_match: str = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> EventPage:
    if date_from and date_to and date_from > date_to:
        raise api_error("INVALID_DATE_RANGE", "date_from must not be after date_to", 422)
    if entity_match not in ("all", "any"):
        raise api_error("INVALID_ENTITY_MATCH", "entity_match must be all or any", 422)
    filters = Filters(
        q=q,
        category=category,
        date_from=date_from,
        date_to=date_to,
        min_importance=min_importance,
        entity_ids=entity_ids or [],
        entity_match=entity_match,
    )
    try:
        page = await repository.list_events(filters, limit, cursor)
    except InvalidCursor as exc:
        raise api_error("INVALID_CURSOR", str(exc), 422) from exc
    except RepositoryUnavailable as exc:
        raise api_error("RETRIEVAL_FAILED", "Database retrieval failed", 503, True) from exc
    return EventPage(
        items=page.items,
        total=page.total,
        next_cursor=page.next_cursor,
        filters_applied=filters,
        as_of=page.as_of,
        data_revision=page.data_revision,
        request_id=str(uuid4()),
        data_mode=data_mode(request),
    )


@app.get("/api/v1/events/{event_id}", response_model=EventDetail)
async def event_detail(
    event_id: UUID,
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> EventDetail:
    item = await repository.event(event_id)
    if item is None:
        raise api_error("EVENT_NOT_FOUND", "Event was not found", 404)
    evidence = await repository.evidence_for(event_id)
    articles = await repository.articles_for(event_id)
    return EventDetail(
        **item.model_dump(), evidence=evidence, articles=articles, data_mode=data_mode(request)
    )


@app.get("/api/v1/events/{event_id}/evidence", response_model=EvidencePage)
async def event_evidence(
    event_id: UUID,
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> EvidencePage:
    if await repository.event(event_id) is None:
        raise api_error("EVENT_NOT_FOUND", "Event was not found", 404)
    return EvidencePage(
        items=await repository.evidence_for(event_id),
        data_mode=data_mode(request),
    )


@app.get("/api/v1/stats")
async def stats(
    request: Request, repository: Annotated[EventRepository, Depends(get_repository)]
) -> dict[str, object]:
    return {
        **await repository.stats(),
        "data_mode": data_mode(request),
        "synthetic": data_mode(request) == "fixture",
    }


@app.get("/api/v1/insights")
async def insights(
    request: Request, repository: Annotated[EventRepository, Depends(get_repository)]
) -> dict[str, object]:
    return {
        **await repository.insights(),
        "data_mode": data_mode(request),
        "synthetic": data_mode(request) == "fixture",
    }


@app.get("/api/v1/sources")
async def sources(
    request: Request, repository: Annotated[EventRepository, Depends(get_repository)]
) -> dict[str, object]:
    return {
        "items": await repository.sources(),
        "data_mode": data_mode(request),
        "synthetic": data_mode(request) == "fixture",
    }


@app.post("/api/v1/ask")
async def ask(
    payload: AskRequest,
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
) -> dict[str, object]:
    has_structured_scope = bool(
        payload.filters.q
        or payload.filters.category
        or payload.filters.date_from
        or payload.filters.date_to
        or payload.filters.min_importance
        or payload.filters.entity_ids
    )
    if not has_structured_scope:
        raise api_error(
            "MODEL_UNAVAILABLE",
            "Question interpretation requires a configured answer model",
            503,
        )
    try:
        page = await repository.list_events(payload.filters, 1, None)
    except RepositoryUnavailable as exc:
        raise api_error("RETRIEVAL_FAILED", "Database retrieval failed", 503, True) from exc
    if page.total == 0:
        return {
            "answer": "",
            "citations": [],
            "execution_status": "completed",
            "answer_status": "no_answer",
            "query_plan_public": payload.filters.model_dump(mode="json"),
            "scope_total": 0,
            "retrieved_count": 0,
            "summarized_count": 0,
            "citation_count": 0,
            "coverage": "complete",
            "as_of": page.as_of,
            "filters_applied": payload.filters,
            "request_id": str(uuid4()),
            "data_mode": data_mode(request),
        }
    if not request.app.state.settings.llm_api_key:
        raise api_error("MODEL_UNAVAILABLE", "Answer model is not configured", 503)
    raise api_error("ASK_NOT_IMPLEMENTED", "Answer generation is not implemented", 503)


def require_admin(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    token = request.app.state.settings.admin_token
    if not token:
        raise api_error(
            "MANAGEMENT_UNAVAILABLE",
            "Administrator credentials are not configured",
            503,
        )
    if authorization != f"Bearer {token}":
        raise api_error("UNAUTHORIZED", "Valid administrator credentials are required", 401)


def ingest_repository(request: Request) -> IngestRepository:
    repository = cast(IngestRepository | None, request.app.state.ingest_repository)
    if repository is None:
        raise api_error(
            "INGEST_NOT_AVAILABLE",
            "Persistent ingest is unavailable outside PostgreSQL mode",
            503,
        )
    return repository


@app.get(
    "/api/v1/ingest/runs",
    response_model=dict[str, list[IngestRun]],
    dependencies=[Depends(require_admin)],
)
async def ingest_runs(request: Request) -> dict[str, list[IngestRun]]:
    repository = ingest_repository(request)
    items = []
    for item in await repository.runs():
        response = IngestRun.model_validate(item).model_copy(
            update={
                "found": item.discovered_urls,
                "kept": 0,
                "candidates": item.event_candidates,
                "versions": item.new_articles + item.updated_articles,
            }
        )
        items.append(response)
    return {"items": items}


@app.post(
    "/api/v1/ingest/runs",
    response_model=IngestRunCreated,
    status_code=202,
    dependencies=[Depends(require_admin)],
)
async def start_ingest(
    payload: IngestRunRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=200)],
) -> IngestRunCreated:
    repository = ingest_repository(request)
    try:
        run, replay = await repository.create_run(payload.source_ids, idempotency_key)
    except IdempotencyConflict as exc:
        raise api_error("IDEMPOTENCY_CONFLICT", str(exc), 409) from exc
    except SourceRejected as exc:
        raise api_error("SOURCE_REJECTED", str(exc), 422) from exc
    return IngestRunCreated(run_id=run.id, status=run.status, idempotent_replay=replay)
