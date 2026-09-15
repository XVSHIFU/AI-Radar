from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing, asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.responses import Response

from .admin_api import router as admin_router
from .admin_api import session_router
from .admin_auth import AdminSessionStore, require_admin
from .config import get_settings
from .data_quality_api import router as data_quality_router
from .fixture_repository import FixtureRepository
from .ingest.dns import configured_resolver
from .ingest_repository import IdempotencyConflict, IngestRepository, SourceRejected
from .model_config import ModelConfigUnavailable, effective_model_settings
from .postgres_repository import PostgresRepository
from .qa_limits import AskAdmission, AskLimitReached
from .qa_service import QaError, answer_question
from .qa_stream_service import StreamContext, prepare_stream, sse, stream_answer
from .queryplanner import InvalidTimezone, QueryPlanner
from .repository import EventRepository, EvidenceInvalid, InvalidCursor, RepositoryUnavailable
from .schemas import (
    AskRequest,
    Category,
    ClarificationCandidate,
    ErrorBody,
    EventDetail,
    EventPage,
    EventTarget,
    EvidencePage,
    Filters,
    IngestRun,
    IngestRunCreated,
    IngestRunRequest,
    InsightsResponse,
    QueryPlan,
)


def api_error(
    code: str,
    message: str,
    status: int,
    retryable: bool = False,
    details: dict[str, object] | None = None,
) -> HTTPException:
    detail: dict[str, object] = {
        "code": code,
        "message": message,
        "retryable": retryable,
        "request_id": str(uuid4()),
    }
    if details is not None:
        detail["details"] = details
    return HTTPException(status_code=status, detail=detail)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.repository = None
    app.state.engine = None
    app.state.ingest_repository = None
    app.state.sessions = None
    app.state.admin_sessions = AdminSessionStore()
    app.state.ask_admission = AskAdmission()
    if settings.radar_data_mode == "fixture":
        path = Path(__file__).resolve().parents[3] / "contracts" / "prototype-events.json"
        app.state.repository = FixtureRepository(path, settings.cursor_secret)
    elif (url := settings.sqlalchemy_url()) is not None:
        engine = create_async_engine(url, pool_pre_ping=True)
        app.state.engine = engine
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        app.state.sessions = sessions
        app.state.ingest_repository = IngestRepository(sessions)
        app.state.repository = PostgresRepository(
            sessions,
            settings.cursor_secret,
            settings.business_timezone,
        )
    yield
    if app.state.engine is not None:
        await app.state.engine.dispose()


app = FastAPI(title="AI Radar API", version="0.1.0", lifespan=lifespan)
app.include_router(session_router)
app.include_router(admin_router)
app.include_router(data_quality_router)


@app.middleware("http")
async def no_store_admin(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    if (
        request.url.path.startswith("/api/v1/admin")
        or request.url.path.startswith("/api/v1/ingest")
        or request.url.path == "/api/v1/sources"
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


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
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if request.url.path == "/api/v1/insights/summary":
        missing_dates = any(
            item["type"] == "missing"
            and item["loc"] in {("query", "date_from"), ("query", "date_to")}
            for item in exc.errors()
        )
        if missing_dates:
            return JSONResponse(
                status_code=422,
                content={
                    "code": "INVALID_DATE_RANGE",
                    "message": "date_from 和 date_to 为必填参数",
                    "retryable": False,
                    "request_id": str(uuid4()),
                },
            )
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "查询参数校验失败",
                "retryable": False,
                "request_id": str(uuid4()),
                "details": {
                    "errors": [
                        {
                            "location": list(item["loc"]),
                            "message": "参数格式或取值无效",
                            "type": item["type"],
                        }
                        for item in exc.errors()
                    ]
                },
            },
        )
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


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "code": "DATABASE_UNAVAILABLE",
            "message": "Database operation failed",
            "retryable": True,
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


def get_clock() -> datetime:
    return datetime.now(UTC)


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


@app.get(
    "/api/v1/insights/summary",
    response_model=InsightsResponse,
    responses={422: {"model": ErrorBody, "description": "查询参数或日期范围无效"}},
)
async def insight_summary(
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    q: str | None = None,
    category: Category | None = None,
    min_importance: Annotated[int | None, Query(ge=1, le=5)] = None,
) -> InsightsResponse:
    if date_from > date_to:
        raise api_error("INVALID_DATE_RANGE", "date_from 不能晚于 date_to", 422)
    if date_to - date_from > timedelta(days=365):
        raise api_error("INVALID_DATE_RANGE", "时间范围最多为 366 天", 422)
    snapshot = await repository.insight_summary(
        Filters(
            q=q,
            category=category,
            min_importance=min_importance,
            date_from=date_from,
            date_to=date_to,
        )
    )
    return InsightsResponse(
        date_from=date_from,
        date_to=date_to,
        timezone=request.app.state.settings.business_timezone,
        total_events=snapshot.total_events,
        daily=[
            {
                "date": date_from + timedelta(days=offset),
                "count": snapshot.daily.get(date_from + timedelta(days=offset), 0),
            }
            for offset in range((date_to - date_from).days + 1)
        ],
        categories=[
            {"category": item, "count": snapshot.categories.get(item, 0)} for item in Category
        ],
        daily_categories=[
            {
                "date": date_from + timedelta(days=offset),
                "category": category_item,
                "count": snapshot.daily_categories.get(
                    (date_from + timedelta(days=offset), category_item), 0
                ),
            }
            for offset in range((date_to - date_from).days + 1)
            for category_item in Category
        ],
        as_of=snapshot.as_of,
        data_revision=snapshot.data_revision,
        data_mode=data_mode(request),
        request_id=str(uuid4()),
    )


@app.get("/api/v1/sources", dependencies=[Depends(require_admin)])
async def sources(
    request: Request, repository: Annotated[EventRepository, Depends(get_repository)]
) -> dict[str, object]:
    return {
        "items": await repository.sources(),
        "data_mode": data_mode(request),
        "synthetic": data_mode(request) == "fixture",
    }


async def create_query_plan(
    payload: AskRequest,
    request: Request,
    repository: EventRepository,
    clock: datetime,
) -> QueryPlan:
    try:
        plan = await QueryPlanner().parse(
            payload.question,
            payload.filters,
            payload.timezone,
            clock,
            repository,
            payload.history,
        )
    except InvalidTimezone as exc:
        raise api_error("VALIDATION_ERROR", "Unknown IANA timezone", 422) from exc
    except ValueError as exc:
        raise api_error("QUERY_INVALID", str(exc), 422) from exc
    if plan.filters.event_ids:
        base_filters = plan.filters.model_copy(update={"event_ids": []})
        targets: list[EventTarget] = []
        warnings = list(plan.warnings)
        candidates = list(plan.clarification_candidates)
        has_conflict = False
        try:
            for event_id in plan.filters.event_ids:
                item = await repository.event(event_id)
                if item is None:
                    status = "not_found"
                    title = None
                    warnings.append(f"附件事件 {event_id} 不存在或未发布")
                    candidates.append(
                        ClarificationCandidate(
                            label=f"移除不存在的附件事件 {event_id}",
                            entity_id=None,
                        )
                    )
                    has_conflict = True
                else:
                    matched = await repository.list_events(
                        base_filters.model_copy(update={"event_ids": [event_id]}),
                        1,
                        None,
                    )
                    status = "matched" if matched.total == 1 else "filtered_out"
                    title = item.title_zh
                    if status == "filtered_out":
                        warnings.append(f"附件事件“{title}”与当前筛选冲突")
                        candidates.append(
                            ClarificationCandidate(
                                label=f"调整筛选以包含附件事件“{title}”",
                                entity_id=None,
                            )
                        )
                        has_conflict = True
                targets.append(EventTarget(event_id=event_id, title_zh=title, status=status))
        except RepositoryUnavailable as exc:
            raise api_error(
                "RETRIEVAL_FAILED",
                "Database retrieval failed while validating event attachments",
                503,
                True,
                {"query_plan_public": plan.model_dump(mode="json")},
            ) from exc
        plan = plan.model_copy(
            update={
                "event_targets": targets,
                "warnings": warnings,
                "clarification_candidates": candidates,
                "requires_clarification": plan.requires_clarification or has_conflict,
            }
        )
    return plan.model_copy(update={"data_mode": data_mode(request), "request_id": str(uuid4())})


@app.post("/api/v1/query-plan", response_model=QueryPlan)
async def query_plan(
    payload: AskRequest,
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
    clock: Annotated[datetime, Depends(get_clock)],
) -> QueryPlan:
    return await create_query_plan(payload, request, repository, clock)


@app.post("/api/v1/ask")
async def ask(
    payload: AskRequest,
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
    clock: Annotated[datetime, Depends(get_clock)],
) -> dict[str, object]:
    plan = await create_query_plan(payload, request, repository, clock)
    public_plan = plan.model_dump(mode="json")
    if request.app.state.sessions is not None:
        try:
            settings = effective_model_settings(request.app.state.settings)
            client = request.client.host if request.client else "unknown"
            with request.app.state.ask_admission.slot(client):
                return await answer_question(
                    payload, plan, repository, request.app.state.sessions, settings
                )
        except ModelConfigUnavailable as exc:
            raise api_error(
                "MODEL_CONFIG_UNAVAILABLE", "模型配置暂不可用，请联系管理员。", 503
            ) from exc
        except AskLimitReached as exc:
            raise api_error("RATE_LIMITED", str(exc), 429, True) from exc
        except QaError as exc:
            raise api_error(exc.code, exc.message, exc.status, exc.retryable, exc.details) from exc
    if plan.requires_clarification:
        raise api_error(
            "CLARIFICATION_REQUIRED",
            "The query needs clarification before execution",
            422,
            details={"query_plan_public": public_plan},
        )
    if plan.free_text:
        raise api_error(
            "QUERY_UNSUPPORTED",
            "Some query constraints are not supported deterministically",
            503,
            details={"query_plan_public": public_plan},
        )
    try:
        page = await repository.list_events(plan.filters, 1, None)
    except RepositoryUnavailable as exc:
        raise api_error(
            "RETRIEVAL_FAILED",
            "Database retrieval failed",
            503,
            True,
            {"query_plan_public": public_plan},
        ) from exc
    if page.total == 0:
        return {
            "answer": "",
            "citations": [],
            "execution_status": "completed",
            "answer_status": "no_answer",
            "query_plan_public": public_plan,
            "scope_total": 0,
            "retrieved_count": 0,
            "summarized_count": 0,
            "citation_count": 0,
            "coverage": "complete",
            "as_of": page.as_of,
            "filters_applied": plan.filters,
            "request_id": str(uuid4()),
            "data_mode": data_mode(request),
        }
    raise api_error(
        "MODEL_UNAVAILABLE",
        "真实回答仅在已配置模型的数据库模式下可用。",
        503,
        details={"query_plan_public": public_plan},
    )


@app.post(
    "/api/v1/ask/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
async def ask_stream(
    payload: AskRequest,
    request: Request,
    repository: Annotated[EventRepository, Depends(get_repository)],
    clock: Annotated[datetime, Depends(get_clock)],
) -> StreamingResponse:
    plan = await create_query_plan(payload, request, repository, clock)
    if request.app.state.sessions is None:
        raise api_error("MODEL_UNAVAILABLE", "真实流式回答仅在数据库模式下可用。", 503)
    client_id = request.client.host if request.client else "unknown"
    admission = request.app.state.ask_admission.slot(client_id)
    try:
        admission.__enter__()
        settings = effective_model_settings(request.app.state.settings)
        prepared = await prepare_stream(
            payload, plan, repository, request.app.state.sessions, settings
        )
    except ModelConfigUnavailable as exc:
        admission.__exit__(type(exc), exc, exc.__traceback__)
        raise api_error(
            "MODEL_CONFIG_UNAVAILABLE", "模型配置暂不可用，请联系管理员。", 503
        ) from exc
    except AskLimitReached as exc:
        raise api_error("RATE_LIMITED", str(exc), 429, True) from exc
    except QaError as exc:
        admission.__exit__(type(exc), exc, exc.__traceback__)
        raise api_error(exc.code, exc.message, exc.status, exc.retryable, exc.details) from exc
    except BaseException as exc:
        admission.__exit__(type(exc), exc, exc.__traceback__)
        raise

    async def body() -> AsyncIterator[bytes]:
        try:
            if isinstance(prepared, StreamContext):
                resolver = configured_resolver(settings.fetch_dns_mode)
                transport = getattr(request.app.state, "answer_stream_transport", None)
                stream = stream_answer(
                    prepared, request.app.state.sessions, settings, resolver, transport=transport
                )
                async with aclosing(stream):
                    async for chunk in stream:
                        yield chunk
            else:
                request_id = str(prepared["request_id"])
                yield sse(
                    "meta",
                    {
                        "request_id": request_id,
                        "protocol_version": 1,
                        **{
                            key: prepared[key]
                            for key in (
                                "query_plan_public",
                                "data_mode",
                                "as_of",
                                "filters_applied",
                            )
                        },
                    },
                )
                yield sse("sources", {"items": []})
                yield sse(
                    "done",
                    {
                        "status": "completed",
                        **{
                            k: prepared[k]
                            for k in (
                                "answer_status",
                                "scope_total",
                                "retrieved_count",
                                "summarized_count",
                                "citation_count",
                                "coverage",
                            )
                        },
                    },
                )
        finally:
            admission.__exit__(None, None, None)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


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
    runs = await repository.runs()
    counts = await repository.published_counts([item.id for item in runs])
    for item in runs:
        response = IngestRun.model_validate(item).model_copy(
            update={
                "found": item.discovered_urls,
                "kept": counts.get(item.id, 0),
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
