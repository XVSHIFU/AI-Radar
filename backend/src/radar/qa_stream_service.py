from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Settings
from .deepseek_client import Completion, ProviderUsage
from .ingest.public_transport import PublicAsyncTransport, Resolver
from .model_stream import ModelStreamError, OpenAiCompatibleStream
from .qa_service import (
    CLIENT_ID,
    MAX_CONTEXT_CHARS,
    MAX_EVENTS,
    MAX_EVIDENCE,
    SYSTEM_PROMPT,
    QaError,
    QaService,
    make_prompt,
    payload_hash,
    validate_answer,
)
from .repository import EventRepository, EvidenceInvalid, RepositoryUnavailable
from .schemas import AskRequest, Event, Evidence, QueryPlan


@dataclass
class StreamContext:
    payload: AskRequest
    plan: QueryPlan
    events: list[Event]
    evidence: list[tuple[Event, Evidence]]
    prompt: str
    base: dict[str, object]
    call_id: UUID


async def prepare_stream(
    payload: AskRequest,
    plan: QueryPlan,
    repo: EventRepository,
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> StreamContext | dict[str, object]:
    public = plan.model_dump(mode="json")
    if plan.requires_clarification:
        raise QaError(
            "CLARIFICATION_REQUIRED",
            "The query needs clarification",
            422,
            details={"query_plan_public": public},
        )
    if plan.free_text:
        raise QaError(
            "QUERY_UNSUPPORTED",
            "Unsupported query constraints",
            503,
            details={"query_plan_public": public},
        )
    if not CLIENT_ID.fullmatch(payload.client_request_id):
        raise QaError(
            "INVALID_CLIENT_REQUEST_ID", "client_request_id must be 1-128 safe characters", 422
        )
    try:
        page = await repo.list_events(plan.filters, MAX_EVENTS, None)
    except RepositoryUnavailable as exc:
        raise QaError("RETRIEVAL_FAILED", "Database retrieval failed", 503, True) from exc
    base: dict[str, object] = {
        "request_id": plan.request_id,
        "query_plan_public": public,
        "data_mode": plan.data_mode or "postgres",
        "as_of": page.as_of,
        "filters_applied": plan.filters.model_dump(mode="json"),
        "scope_total": page.total,
        "retrieved_count": len(page.items),
        "retrieval_snapshot": page.data_revision,
        "coverage": "complete" if page.total <= len(page.items) else "partial",
    }
    if not page.total:
        return {**base, "answer_status": "no_answer", "summarized_count": 0, "citation_count": 0}
    evidence: list[tuple[Event, Evidence]] = []
    chars = 0
    try:
        for event in page.items:
            for item in sorted(
                await repo.evidence_for(event.id),
                key=lambda x: (str(x.source_url), x.paragraph_id, str(x.id)),
            ):
                size = (
                    len(event.title_zh)
                    + len(item.title)
                    + len(item.quote_text)
                    + len(item.paragraph_id)
                )
                if len(evidence) >= MAX_EVIDENCE or chars + size > MAX_CONTEXT_CHARS:
                    base["coverage"] = "partial"
                    continue
                evidence.append((event, item))
                chars += size
    except (RepositoryUnavailable, EvidenceInvalid) as exc:
        raise QaError("RETRIEVAL_FAILED", "Evidence retrieval failed", 503, True) from exc
    if not evidence:
        base["coverage"] = "partial"
        return {**base, "answer_status": "no_answer", "summarized_count": 0, "citation_count": 0}
    pp = payload
    prompt = make_prompt(pp, page.items, evidence)
    if len(prompt) > MAX_CONTEXT_CHARS and payload.history:
        pp = payload.model_copy(update={"history": []})
        prompt = make_prompt(pp, page.items, evidence)
    while len(prompt) > MAX_CONTEXT_CHARS and len(evidence) > 1:
        evidence.pop()
        base["coverage"] = "partial"
        prompt = make_prompt(pp, page.items, evidence)
    if len(prompt) > MAX_CONTEXT_CHARS:
        raise QaError("CONTEXT_TOO_LARGE", "Frozen evidence exceeds context limit", 422)
    evidenced = {e.id for e, _ in evidence}
    if len(evidenced) < len(page.items):
        base["coverage"] = "partial"
    if not settings.llm_api_key:
        raise QaError("MODEL_UNAVAILABLE", "Answer model is not configured", 503)
    ledger = QaService(
        sessions,
        None,
        provider=getattr(settings, "llm_provider", "deepseek"),
        model=settings.llm_model,
    )
    call_id = await ledger.claim(payload.client_request_id, payload_hash(payload, plan))
    return StreamContext(payload, plan, page.items, evidence, prompt, base, call_id)


def sse(event: str, data: dict[str, object]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode()


async def stream_answer(
    ctx: StreamContext,
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
    resolver: Resolver,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncGenerator[bytes, None]:
    request_id = str(ctx.base["request_id"])
    ledger = QaService(
        sessions,
        None,
        provider=getattr(settings, "llm_provider", "deepseek"),
        model=settings.llm_model,
    )
    answer = ""
    seq = 0
    usage: ProviderUsage | None = None
    response_id: str | None = None
    provider_started = False
    terminal_written = False
    client = OpenAiCompatibleStream(
        settings.llm_api_key or "",
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        transport=transport or PublicAsyncTransport(resolver=resolver),
    )
    try:
        yield sse(
            "meta",
            {
                "request_id": request_id,
                "protocol_version": 1,
                **{
                    key: ctx.base[key]
                    for key in (
                        "query_plan_public",
                        "data_mode",
                        "as_of",
                        "filters_applied",
                    )
                },
            },
        )
        yield sse("status", {"phase": "generating", "message": "正在基于冻结证据生成回答"})
        provider_started = True
        stream_prompt = SYSTEM_PROMPT.replace(
            "只返回JSON对象，字段为answer字符串和citation_indices整数数组。",
            "直接输出回答正文和[编号]引用，不要输出JSON、代码围栏或思考过程。",
        )
        async for delta in client.stream(system=stream_prompt, user=ctx.prompt):
            response_id = delta.response_id or response_id
            if delta.usage is not None:
                usage = delta.usage
            if delta.text:
                if len(answer) + len(delta.text) > 12_000:
                    raise ValueError("answer exceeds streaming limit")
                answer += delta.text
                seq += 1
                yield sse("token", {"seq": seq, "text": delta.text})
        parsed = validate_answer(
            json.dumps(
                {
                    "answer": answer,
                    "citation_indices": sorted(
                        {int(x) for x in __import__("re").findall(r"\[(\d+)]", answer)}
                    ),
                }
            ),
            len(ctx.evidence),
        )
        completion = Completion(answer, response_id, usage or ProviderUsage())
        await ledger.mark(ctx.call_id, "completed", completion, None)
        terminal_written = True
        citations = []
        for i in parsed.citation_indices:
            event, item = ctx.evidence[i - 1]
            citations.append(
                {
                    "index": i,
                    "evidence_id": str(item.id),
                    "event_id": str(event.id),
                    "article_version_id": str(item.article_version_id),
                    "paragraph_id": item.paragraph_id,
                    "quote_text": item.quote_text,
                    "source_url": str(item.source_url),
                    "title": item.title,
                    "verification_status": item.verification_status,
                }
            )
        count = len({ctx.evidence[i - 1][0].id for i in parsed.citation_indices})
        if count != ctx.base["scope_total"]:
            ctx.base["coverage"] = "partial"
        yield sse("sources", {"items": citations})
        yield sse(
            "done",
            {
                "status": "completed",
                "answer_status": "answered",
                **{k: ctx.base[k] for k in ("scope_total", "retrieved_count", "coverage")},
                "summarized_count": count,
                "citation_count": len(citations),
            },
        )
    except (asyncio.CancelledError, GeneratorExit):
        if not terminal_written:
            cancelled_completion = (
                Completion(answer, response_id, usage or ProviderUsage())
                if answer or usage or response_id
                else None
            )
            await asyncio.shield(
                ledger.mark(
                    ctx.call_id,
                    "unknown" if provider_started else "cancelled",
                    cancelled_completion,
                    "cancelled_outcome_unknown" if provider_started else "cancelled_before_request",
                )
            )
        raise
    except (ModelStreamError, ValueError) as exc:
        unknown = isinstance(exc, ModelStreamError) and exc.unknown
        if isinstance(exc, ModelStreamError):
            usage = exc.usage or usage
            response_id = exc.response_id or response_id
            code = exc.code
        else:
            code = "invalid_answer"
        failure_completion = (
            Completion(answer, response_id, usage or ProviderUsage()) if answer or usage else None
        )
        await ledger.mark(ctx.call_id, "unknown" if unknown else "failed", failure_completion, code)
        yield sse(
            "error",
            {
                "code": (
                    "MODEL_OUTCOME_UNKNOWN"
                    if unknown
                    else "MODEL_INVALID_RESPONSE"
                    if code == "invalid_answer"
                    else "MODEL_FAILED"
                ),
                "message": "回答流中断，未自动重试。",
                "retryable": False,
                "request_id": request_id,
            },
        )
        yield sse("sources", {"items": []})
        yield sse(
            "done",
            {
                "status": "failed",
                "answer_status": None,
                **{k: ctx.base[k] for k in ("scope_total", "retrieved_count")},
                "summarized_count": 0,
                "citation_count": 0,
                "coverage": "partial",
            },
        )
    finally:
        await client.close()
