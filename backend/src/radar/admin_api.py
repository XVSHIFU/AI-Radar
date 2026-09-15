from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .admin_auth import SESSION_COOKIE, AdminSessionStore, admin_error, require_admin
from .deepseek_client import DeepSeekClient, DeepSeekError, ProviderUsage
from .ingest.core import (
    UnsafeUrl,
    canonicalize_url,
    fetch_public,
    parse_feed,
    resolve_public,
)
from .ingest.dns import configured_resolver
from .ingest.public_transport import PublicAsyncTransport
from .model_config import (
    PRESETS,
    EffectiveModelConfig,
    ModelConfigStore,
    ModelConfigUnavailable,
    normalize_base_url,
)
from .models import LlmCallRow, SourceRow

BUILTIN_SOURCES = {
    "Hugging Face",
    "arXiv cs.AI",
    "Google Research",
    "AWS Machine Learning",
    "NVIDIA Technical Blog",
    "OpenAI",
    "Anthropic",
    "DeepSeek",
}

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])
session_router = APIRouter(prefix="/api/v1/admin/session")


class SessionLogin(BaseModel):
    token: str = Field(min_length=1, max_length=1000)


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    feed_url: str = Field(min_length=1, max_length=4000)
    channel_type: Literal["rss"]

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("feed_url")
    @classmethod
    def safe_feed_url(cls, value: str) -> str:
        return canonicalize_url(value)


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    feed_url: str | None = Field(default=None, min_length=1, max_length=4000)
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("feed_url")
    @classmethod
    def safe_feed_url(cls, value: str | None) -> str | None:
        return canonicalize_url(value) if value is not None else None


class ModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str | None = Field(default=None, max_length=2000)
    enabled: bool
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=1, max_length=2000)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    max_tokens: int = Field(ge=1, le=2000)


class ModelTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["connectivity", "completion"]


def _sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    sessions = cast(async_sessionmaker[AsyncSession] | None, request.app.state.sessions)
    if sessions is None:
        raise admin_error("DATABASE_UNAVAILABLE", "PostgreSQL is not configured", 503)
    return sessions


def _source(row: SourceRow) -> dict[str, object]:
    return {
        "id": str(row.id),
        "name": row.name,
        "feed_url": row.feed_url,
        "enabled": row.enabled,
        "health": row.health,
        "last_success_at": row.last_success_at,
        "consecutive_failures": row.consecutive_failures,
        "channel_type": row.channel_type,
        "last_checked_at": row.last_checked_at,
        "cooldown_until": row.cooldown_until,
        "editable": row.name not in BUILTIN_SOURCES,
    }


@session_router.post("")
async def login(payload: SessionLogin, request: Request) -> JSONResponse:
    store: AdminSessionStore = request.app.state.admin_sessions
    client = request.client.host if request.client else "unknown"
    token, session = store.login(payload.token, request.app.state.settings.admin_token, client)
    response = JSONResponse(
        {
            "authenticated": True,
            "csrf_token": session.csrf_token,
            "expires_at": session.expires_at.isoformat(),
        }
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=8 * 60 * 60,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@session_router.get("")
async def current_session(request: Request) -> JSONResponse:
    store: AdminSessionStore = request.app.state.admin_sessions
    session = store.get(request.cookies.get(SESSION_COOKIE))
    body: dict[str, object] = {"authenticated": session is not None}
    if session is not None:
        body.update(csrf_token=session.csrf_token, expires_at=session.expires_at.isoformat())
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@session_router.delete("", status_code=204, dependencies=[Depends(require_admin)])
async def logout(request: Request) -> Response:
    store: AdminSessionStore = request.app.state.admin_sessions
    store.logout(request.cookies.get(SESSION_COOKIE))
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/sources")
async def list_sources(request: Request) -> dict[str, object]:
    async with _sessions(request)() as session:
        rows = list((await session.scalars(select(SourceRow).order_by(SourceRow.name))).all())
    return {"items": [_source(row) for row in rows]}


@router.post("/sources", status_code=201)
async def create_source(payload: SourceCreate, request: Request) -> dict[str, object]:
    resolver = configured_resolver(request.app.state.settings.fetch_dns_mode)
    try:
        await resolve_public(payload.feed_url, resolver)
    except UnsafeUrl as exc:
        raise admin_error("SOURCE_URL_UNSAFE", str(exc), 422) from exc
    host = urlsplit(payload.feed_url).hostname
    assert host is not None
    row = SourceRow(
        id=uuid4(),
        name=payload.name,
        feed_url=payload.feed_url,
        enabled=False,
        health="unknown",
        consecutive_failures=0,
        canonical_host=host.casefold(),
        channel_type="rss",
    )
    try:
        async with _sessions(request)() as session, session.begin():
            session.add(row)
    except IntegrityError as exc:
        raise admin_error("SOURCE_ALREADY_EXISTS", "Source name already exists", 409) from exc
    return _source(row)


@router.patch("/sources/{source_id}")
async def patch_source(
    source_id: UUID, payload: SourcePatch, request: Request
) -> dict[str, object]:
    values = payload.model_dump(exclude_unset=True)
    if any(value is None for value in values.values()):
        raise admin_error("SOURCE_PATCH_INVALID", "Patch fields cannot be null", 422)
    if "feed_url" in values:
        resolver = configured_resolver(request.app.state.settings.fetch_dns_mode)
        try:
            await resolve_public(cast(str, values["feed_url"]), resolver)
        except UnsafeUrl as exc:
            raise admin_error("SOURCE_URL_UNSAFE", str(exc), 422) from exc
        host = urlsplit(cast(str, values["feed_url"])).hostname
        assert host is not None
        values.update(
            canonical_host=host.casefold(),
            health="unknown",
            last_checked_at=None,
            etag=None,
            last_modified=None,
            consecutive_failures=0,
            cooldown_until=None,
        )
    try:
        async with _sessions(request)() as session, session.begin():
            row = await session.get(SourceRow, source_id, with_for_update=True)
            if row is None:
                raise admin_error("SOURCE_NOT_FOUND", "Source was not found", 404)
            if row.name in BUILTIN_SOURCES and any(key in values for key in ("name", "feed_url")):
                raise admin_error(
                    "SOURCE_IMMUTABLE",
                    "Built-in archive source metadata is read-only",
                    422,
                )
            for key, value in values.items():
                setattr(row, key, value)
    except IntegrityError as exc:
        raise admin_error("SOURCE_ALREADY_EXISTS", "Source name already exists", 409) from exc
    return _source(row)


@router.post("/sources/{source_id}/probe")
async def probe_source(source_id: UUID, request: Request) -> dict[str, object]:
    sessions = _sessions(request)
    async with sessions() as session:
        row = await session.get(SourceRow, source_id)
        if row is None:
            raise admin_error("SOURCE_NOT_FOUND", "Source was not found", 404)
        now = datetime.now(UTC)
        if row.cooldown_until is not None and row.cooldown_until > now:
            raise admin_error("SOURCE_COOLDOWN", "Source is cooling down", 429)
        if row.last_checked_at is not None and row.last_checked_at > now - timedelta(seconds=30):
            raise admin_error("SOURCE_PROBE_RATE_LIMITED", "Probe was run recently", 429)
        feed_url = row.feed_url
        channel_type = row.channel_type
    checked_at = datetime.now(UTC)
    resolver = configured_resolver(request.app.state.settings.fetch_dns_mode)
    transport = getattr(request.app.state, "admin_http_transport", None)
    client = httpx.AsyncClient(
        transport=transport or PublicAsyncTransport(resolver=resolver),
        follow_redirects=False,
        trust_env=False,
    )
    ok = False
    status: int | None = None
    items_found: int | None = None
    message = "来源探测失败"
    try:
        result = await fetch_public(client, feed_url, resolver=resolver)
        status = result.status
        if channel_type == "rss":
            items_found = len(parse_feed(result.body))
            message = "RSS 订阅可访问"
        else:
            message = "归档页面可访问"
        ok = True
    except (httpx.HTTPError, UnsafeUrl, ValueError):
        pass
    finally:
        await client.aclose()
    async with sessions() as session, session.begin():
        locked = await session.get(SourceRow, source_id, with_for_update=True)
        assert locked is not None
        locked.last_checked_at = checked_at
        locked.health = "healthy" if ok else "unhealthy"
        locked.consecutive_failures = 0 if ok else locked.consecutive_failures + 1
    body: dict[str, object] = {"ok": ok, "checked_at": checked_at, "message": message}
    if status is not None:
        body["http_status"] = status
    if items_found is not None:
        body["items_found"] = items_found
    return body


def _model_body(config: object) -> dict[str, object]:
    value = cast(EffectiveModelConfig, config)
    return {
        "provider": value.provider,
        "base_url": value.base_url,
        "model": value.model,
        "configured": bool(value.api_key),
        "enabled": value.enabled,
        "max_tokens": value.max_tokens,
    }


def _read_model(request: Request) -> EffectiveModelConfig:
    try:
        return ModelConfigStore(request.app.state.settings).read()
    except ModelConfigUnavailable as exc:
        raise admin_error("MODEL_CONFIG_UNAVAILABLE", str(exc), 503) from exc


@router.get("/model/presets")
async def model_presets() -> dict[str, object]:
    return {"items": list(PRESETS)}


@router.get("/model")
async def get_model(request: Request) -> dict[str, object]:
    return _model_body(_read_model(request))


@router.put("/model")
async def put_model(payload: ModelUpdate, request: Request) -> dict[str, object]:
    store = ModelConfigStore(request.app.state.settings)
    current = _read_model(request)
    try:
        candidate_base = (
            normalize_base_url(payload.base_url) if payload.base_url else current.base_url
        )
        endpoint_changed = candidate_base != current.base_url
        if payload.enabled and (endpoint_changed or not current.enabled):
            resolver = configured_resolver(request.app.state.settings.fetch_dns_mode)
            await resolve_public(candidate_base, resolver)
        config = store.update(
            api_key=payload.api_key,
            enabled=payload.enabled,
            max_tokens=payload.max_tokens,
            provider=payload.provider,
            base_url=payload.base_url,
            model=payload.model,
        )
    except (ModelConfigUnavailable, UnsafeUrl, OSError) as exc:
        raise admin_error("MODEL_CONFIG_INVALID", str(exc), 422) from exc
    return _model_body(config)


async def _record_admin_test(
    sessions: async_sessionmaker[AsyncSession],
    call_id: UUID,
    *,
    status: str,
    usage: ProviderUsage | None = None,
    error_code: str | None = None,
) -> None:
    values = {
        "status": status,
        "error_code": error_code,
        "finished_at": datetime.now(UTC),
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
    }
    async with sessions() as session, session.begin():
        await session.execute(update(LlmCallRow).where(LlmCallRow.id == call_id).values(**values))


TEST_MESSAGES = [
    {"role": "system", "content": "你是模型连接测试助手，只返回 JSON。"},
    {"role": "user", "content": '请返回 {"message":"连接成功"}。'},
]


def _test_result(
    *,
    ok: bool,
    message: str,
    model: str,
    error_code: str | None = None,
    usage: dict[str, int | None] | None = None,
    response_text: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "ok": ok,
        "message": message,
        "model": model,
        "request_messages": TEST_MESSAGES,
    }
    if error_code is not None:
        body["error_code"] = error_code
    if usage is not None:
        body["usage"] = usage
    if response_text is not None:
        body["response_text"] = response_text[:1000]
    return body


@router.post("/model/test")
async def test_model(payload: ModelTestRequest, request: Request) -> dict[str, object]:
    config = _read_model(request)
    if not config.enabled or not config.api_key:
        raise admin_error("MODEL_UNAVAILABLE", "模型未启用或未配置密钥", 422)
    resolver = configured_resolver(request.app.state.settings.fetch_dns_mode)
    transport = getattr(request.app.state, "admin_model_transport", None)
    selected_transport = transport or PublicAsyncTransport(resolver=resolver)
    if payload.kind == "connectivity":
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else None
        try:
            async with httpx.AsyncClient(
                base_url=config.base_url.rstrip("/") + "/",
                transport=selected_transport,
                timeout=20,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.get("models", headers=headers)
                if response.status_code in {404, 405}:
                    return _test_result(
                        ok=False,
                        message="当前服务不支持模型列表接口",
                        model=config.model,
                        error_code="model_list_unsupported",
                    )
                response.raise_for_status()
                data = response.json()
                models = data.get("data", []) if isinstance(data, dict) else []
                if not any(
                    isinstance(item, dict) and item.get("id") == config.model for item in models
                ):
                    return _test_result(
                        ok=False,
                        message="模型列表中未找到当前模型",
                        model=config.model,
                        error_code="model_not_found",
                    )
            return _test_result(ok=True, message="连接成功，已找到当前模型", model=config.model)
        except (httpx.HTTPError, ValueError):
            return _test_result(
                ok=False,
                message="模型连接测试失败",
                model=config.model,
                error_code="connectivity_failed",
            )
    sessions = _sessions(request)
    call_id = uuid4()
    async with sessions() as session, session.begin():
        session.add(
            LlmCallRow(
                id=call_id,
                ingest_run_id=None,
                article_version_id=None,
                logical_request_id=f"admin-test:{call_id}",
                purpose="admin_test",
                provider=config.provider,
                model_id=config.model,
                attempt=1,
                status="pending",
            )
        )
    model_client = DeepSeekClient(
        config.api_key,
        base_url=config.base_url,
        model=config.model,
        provider=config.provider,
        max_tokens=min(config.max_tokens, 32),
        transport=selected_transport,
        resolver=resolver,
    )
    try:
        completion = await model_client.complete_json(
            system=TEST_MESSAGES[0]["content"], user=TEST_MESSAGES[1]["content"]
        )
        await _record_admin_test(sessions, call_id, status="completed", usage=completion.usage)
        usage = {
            "prompt_tokens": completion.usage.prompt_tokens,
            "completion_tokens": completion.usage.completion_tokens,
            "total_tokens": completion.usage.total_tokens,
        }
        return _test_result(
            ok=True,
            message="模型短对话测试成功",
            model=config.model,
            usage=usage,
            response_text=completion.content,
        )
    except DeepSeekError as exc:
        status = "unknown" if exc.code == "unknown_transport_failure" else "failed"
        await _record_admin_test(
            sessions,
            call_id,
            status=status,
            usage=exc.completion.usage if exc.completion else None,
            error_code=exc.code,
        )
        return _test_result(
            ok=False,
            message=str(exc),
            model=config.model,
            error_code=exc.code,
            response_text=exc.completion.content if exc.completion else None,
        )
    finally:
        await model_client.close()


@router.get("/model/usage")
async def model_usage(request: Request) -> dict[str, object]:
    async with _sessions(request)() as session:
        rows = (
            await session.execute(
                select(
                    LlmCallRow.purpose,
                    LlmCallRow.status,
                    func.count(),
                    func.count(LlmCallRow.total_tokens),
                    func.sum(LlmCallRow.prompt_tokens),
                    func.sum(LlmCallRow.completion_tokens),
                    func.sum(LlmCallRow.total_tokens),
                )
                .group_by(LlmCallRow.purpose, LlmCallRow.status)
                .order_by(LlmCallRow.purpose, LlmCallRow.status)
            )
        ).all()
    return {
        "items": [
            {
                "purpose": purpose,
                "status": status,
                "calls": int(calls),
                "usage_recorded": int(recorded),
                "input_tokens": int(prompt) if prompt is not None else None,
                "output_tokens": int(completion) if completion is not None else None,
                "total_tokens": int(total) if total is not None else None,
            }
            for purpose, status, calls, recorded, prompt, completion, total in rows
        ],
        "as_of": datetime.now(UTC),
    }
