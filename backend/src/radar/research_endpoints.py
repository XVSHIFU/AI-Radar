"""Feature-gated public entrypoints; both forms share the same admitted research run."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from .model_config import ModelConfigUnavailable, effective_model_settings
from .postgres_repository import PostgresRepository
from .public_assistant import begin_public_run
from .qa_limits import AskLimitReached
from .qa_service import QaError
from .qa_stream_service import sse
from .repository import EventRepository
from .research_service import research_answer_stream, research_preflight, runtime_client
from .schemas import AskRequest, QueryPlan


async def public_research_response(
    payload: AskRequest,
    plan: QueryPlan,
    request: Request,
    repository: EventRepository,
    *,
    streaming: bool,
) -> StreamingResponse | dict[str, Any]:
    if not isinstance(repository, PostgresRepository) or request.app.state.research_policy is None:
        raise HTTPException(
            503,
            detail={
                "code": "MODEL_UNAVAILABLE",
                "message": "研究服务暂不可用。",
                "retryable": False,
            },
        )
    runtime = None
    run = None
    admitted = False
    admission = request.app.state.ask_admission.slot(
        request.client.host if request.client else "unknown"
    )
    try:
        settings = effective_model_settings(request.app.state.settings)
        runtime = runtime_client(
            settings.research_runtime_url, settings.research_runtime_token or ""
        )
        admission.__enter__()
        admitted = True
        await research_preflight(runtime, plan, settings, request.app.state.research_policy)
        run = await begin_public_run(request, payload, plan)
        if run is None:
            raise QaError("MODEL_UNAVAILABLE", "研究服务需要持久化配额。", 503)
    except BaseException as exc:
        if run:
            await run.finish(completed=False)
        if runtime:
            await runtime.aclose()
        if admitted:
            admission.__exit__(None, None, None)
        if isinstance(exc, QaError):
            raise HTTPException(
                exc.status,
                detail={
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": False,
                    "details": exc.details,
                },
            ) from exc
        if isinstance(exc, (AskLimitReached, ModelConfigUnavailable, ValueError)):
            raise HTTPException(
                429 if isinstance(exc, AskLimitReached) else 503,
                detail={
                    "code": "ASK_BUSY" if isinstance(exc, AskLimitReached) else "MODEL_UNAVAILABLE",
                    "message": "研究服务暂不可用，请稍后再试。",
                    "retryable": False,
                },
            ) from exc
        raise

    async def body() -> AsyncGenerator[bytes, None]:
        completed = False
        try:
            async with asyncio.timeout(run.seconds_left):
                stream = research_answer_stream(
                    run,
                    plan,
                    repository,
                    settings,
                    request.app.state.research_policy,
                    request.app.state.research_sessions,
                    runtime,
                    provider_transport=getattr(request.app.state, "answer_stream_transport", None),
                )
                async with aclosing(stream):
                    async for frame in stream:
                        if frame.startswith(b"event: done\n"):
                            terminal = json.loads(frame.decode("utf-8").split("\ndata: ", 1)[1])
                            completed = terminal.get("status") == "completed"
                        yield frame
        except TimeoutError:
            if completed:
                return
            yield sse(
                "error",
                {
                    "code": "ANSWER_TIMEOUT",
                    "message": "研究超时，当前内容仅为草稿。",
                    "retryable": False,
                    "request_id": str(plan.request_id),
                },
            )
            yield sse("sources", {"items": []})
            yield sse("done", {"status": "failed"})
        finally:
            try:
                await run.finish(completed=completed)
            finally:
                admission.__exit__(None, None, None)
                await runtime.aclose()

    if streaming:
        return StreamingResponse(
            body(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
    result: dict[str, Any] = {"answer": "", "citations": []}
    async with aclosing(body()) as frames:
        async for frame in frames:
            name, data = frame.decode("utf-8").strip().split("\ndata: ", 1)
            item = json.loads(data)
            if name == "event: meta":
                result.update(item)
            elif name == "event: reset":
                result["answer"] = item["text"]
            elif name == "event: token":
                result["answer"] += item["text"]
            elif name == "event: sources":
                result["citations"] = item["items"]
            elif name == "event: done":
                result.update(item)
                result["execution_status"] = "completed"
            elif name == "event: error":
                raise HTTPException(502, detail=item)
    if result.get("execution_status") != "completed":
        raise HTTPException(502, detail={"code": "RESEARCH_INCOMPLETE", "message": "研究未完成。"})
    return result
