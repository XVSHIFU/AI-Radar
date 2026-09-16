"""Private callback router for the pi runtime; never expose it at the public gateway."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .model_stream import ModelStreamError
from .research_gateway import ResearchSession
from .research_guard import ResearchRejected, canonical
from .research_stream import strict_json


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _ModelRequest(_Request):
    # Compatibility with pi's streamFn only. This context is ignored by the trusted
    # session; accepting it cannot override server-owned system/history/tool results.
    context: dict[str, Any]
    sequence: int = Field(ge=1, le=3)
    max_output: int = Field(ge=1, le=2000)


class _ToolRequest(_Request):
    name: Literal[
        "resolve_entities",
        "search_events",
        "get_event_evidence",
        "aggregate_events",
        "compare_periods",
        "build_chart",
        "load_research_skill",
        "run_python",
    ]
    args: dict[str, Any]
    call_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")


class ResearchSessions:
    """Owner of live session lookup, not a persistent transcript or quota replacement."""

    def __init__(self) -> None:
        self._sessions: dict[str, ResearchSession] = {}

    @asynccontextmanager
    async def register(self, session: ResearchSession) -> AsyncIterator[None]:
        if len(self._sessions) >= 2:
            raise ResearchRejected("RUN_BUSY")
        session.guard.check(session.guard.capability)
        key = hashlib.sha256(session.guard.capability.encode()).hexdigest()
        if key in self._sessions:
            raise ResearchRejected("IDEMPOTENCY_REPLAY")
        self._sessions[key] = session
        try:
            yield
        finally:
            self._sessions.pop(key, None)
            session.guard.close()

    def authenticated(self, request: Request) -> tuple[ResearchSession, str]:
        headers = request.headers.getlist("authorization")
        if len(headers) != 1 or not headers[0].startswith("Bearer "):
            raise ResearchRejected("RUN_NOT_FOUND")
        capability = headers[0][7:]
        if not 32 <= len(capability) <= 128 or not capability.isascii():
            raise ResearchRejected("RUN_NOT_FOUND")
        session = self._sessions.get(hashlib.sha256(capability.encode()).hexdigest())
        if session is None:
            raise ResearchRejected("RUN_NOT_FOUND")
        session.guard.check(capability)
        return session, capability


async def _body(request: Request) -> object:
    content = bytearray()
    async for part in request.stream():
        if len(content) + len(part) > 65536:
            raise ResearchRejected("RESOURCE_LIMIT")
        content.extend(part)
    try:
        return strict_json(content.decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise ResearchRejected("INVALID_ARGUMENT") from exc


def _failure(code: str) -> JSONResponse:
    allowed = {
        "RUN_NOT_FOUND": 401,
        "RUN_EXPIRED": 410,
        "RUN_BUSY": 429,
        "IDEMPOTENCY_REPLAY": 409,
        "BUDGET_EXCEEDED": 429,
        "INVALID_ARGUMENT": 400,
        "INVALID_TOOL_CALL": 400,
        "RESOURCE_LIMIT": 413,
    }
    return JSONResponse(
        {"error": {"code": code if code in allowed else "TOOL_UNAVAILABLE"}},
        status_code=allowed.get(code, 502),
    )


def research_router(sessions: ResearchSessions) -> APIRouter:
    router = APIRouter(prefix="/internal/research", include_in_schema=False)

    @router.post("/model", response_model=None)
    async def model(request: Request) -> JSONResponse | StreamingResponse:
        try:
            session, capability = sessions.authenticated(request)
            payload = _ModelRequest.model_validate(await _body(request))
        except ResearchRejected as exc:
            return _failure(exc.code)
        except ValidationError:
            return _failure("INVALID_ARGUMENT")

        async def events() -> AsyncIterator[bytes]:
            stream = session.model(capability, payload.sequence, payload.max_output)
            try:
                async for item in stream:
                    yield (canonical(item) + "\n").encode("utf-8")
            except ResearchRejected as exc:
                # No success terminator on failure. The Node broker fails closed on
                # this terminal envelope; raw provider errors never reach the caller.
                yield (
                    canonical(
                        {
                            "error": {
                                "code": exc.code
                                if exc.code
                                in {
                                    "RUN_EXPIRED",
                                    "RUN_BUSY",
                                    "BUDGET_EXCEEDED",
                                    "RESOURCE_LIMIT",
                                    "IDEMPOTENCY_REPLAY",
                                    "INVALID_TOOL_CALL",
                                }
                                else "TOOL_UNAVAILABLE"
                            }
                        }
                    )
                    + "\n"
                ).encode()
            except (ModelStreamError, Exception):
                yield b'{"error":{"code":"TOOL_UNAVAILABLE"}}\n'
            finally:
                await stream.aclose()

        return StreamingResponse(
            events(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @router.post("/tool")
    async def tool(request: Request) -> JSONResponse:
        try:
            session, capability = sessions.authenticated(request)
            payload = _ToolRequest.model_validate(await _body(request))
            result = await session.tool(capability, payload.name, payload.args, payload.call_id)
            return JSONResponse({"result": result}, headers={"Cache-Control": "no-store"})
        except ResearchRejected as exc:
            return _failure(exc.code)
        except ValidationError:
            return _failure("INVALID_ARGUMENT")

    return router
