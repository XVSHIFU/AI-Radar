"""Public research run assembly and validated SSE output, behind a deployment switch."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Any
from urllib.parse import urlsplit

import httpx

from .config import Settings
from .ingest.dns import configured_resolver
from .ingest.public_transport import PublicAsyncTransport
from .postgres_repository import PostgresRepository
from .public_assistant import PublicRun
from .qa_service import QaError
from .qa_stream_service import sse
from .research_artifacts import ArtifactStore
from .research_gateway import ResearchSession
from .research_guard import ResearchGuard, ResearchRejected, canonical
from .research_http import ResearchSessions
from .research_ledger import PostgresResearchLedger
from .research_memory import prompt_memory
from .research_policy import ANSWER_CONTRACT, ResearchPolicy
from .research_stream import ResearchModelStream, strict_json
from .research_tools import ResearchTools, research_scope
from .sandbox_client import SandboxClient
from .schemas import AskRequest, QueryPlan


def runtime_client(origin: str, token: str) -> httpx.AsyncClient:
    parts = urlsplit(origin)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
        or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token)
    ):
        raise ValueError("invalid server-owned research runtime configuration")
    return httpx.AsyncClient(
        base_url=origin,
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
        trust_env=False,
        follow_redirects=False,
    )


async def research_preflight(
    client: httpx.AsyncClient,
    plan: QueryPlan,
    settings: Settings,
    policy: ResearchPolicy,
    *,
    sandbox: SandboxClient | None = None,
) -> None:
    if plan.requires_clarification:
        raise QaError(
            "CLARIFICATION_REQUIRED",
            "请先明确研究范围。",
            422,
            details={"query_plan_public": plan.model_dump(mode="json")},
        )
    if not settings.llm_api_key:
        raise QaError("MODEL_UNAVAILABLE", "研究模型暂未配置。", 503)
    try:
        response = await client.get("/health", timeout=3)
        health = response.json()
        if (
            response.status_code != 200
            or not isinstance(health, dict)
            or health.get("status") != "ready"
            or health.get("policy_digest") != policy.digest
            or health.get("python", False) is not policy.contract["python"]["enabled"]
        ):
            raise ValueError("runtime not ready")
        if policy.contract["python"]["enabled"]:
            if sandbox is None:
                raise ResearchRejected("SANDBOX_UNAVAILABLE")
            await sandbox.ready(settings.sandbox_image_id)
    except (httpx.HTTPError, ValueError, ResearchRejected) as exc:
        raise QaError("MODEL_UNAVAILABLE", "研究服务暂不可用，请稍后再试。", 503) from exc


async def runtime_events(
    client: httpx.AsyncClient,
    prompt: str,
    max_output: int,
    capability: str,
) -> AsyncGenerator[dict[str, Any], None]:
    pending = bytearray()
    total = 0
    terminal = False
    async with client.stream(
        "POST",
        "/v1/run",
        json={
            "prompt": prompt,
            "max_output": max_output,
            "capability": capability,
        },
    ) as response:
        if response.status_code != 200:
            raise ResearchRejected("TOOL_UNAVAILABLE")
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > 262144:
                raise ResearchRejected("RESOURCE_LIMIT")
            pending.extend(chunk)
            while b"\n" in pending:
                raw, _, rest = pending.partition(b"\n")
                pending = bytearray(rest)
                if len(raw) > 65536 or terminal:
                    raise ResearchRejected("INVALID_MODEL_STREAM")
                item = strict_json(raw.decode("utf-8"))
                if not isinstance(item, dict) or item.get("type") not in {
                    "turn",
                    "text",
                    "tool",
                    "result",
                }:
                    raise ResearchRejected("INVALID_MODEL_STREAM")
                terminal = item["type"] == "result"
                yield item
            if len(pending) > 65536:
                raise ResearchRejected("RESOURCE_LIMIT")
    if pending or not terminal:
        raise ResearchRejected("INVALID_MODEL_STREAM")


def make_research_prompt(payload: AskRequest, plan: QueryPlan, tools: ResearchTools) -> str:
    # Keep whole user/assistant pairs; truncation must not invent an orphan reply.
    pairs: list[list[dict[str, Any]]] = []
    user = None
    for message in payload.history:
        if message.role == "user":
            user = message
        elif user is not None:
            pairs.append(
                [
                    {
                        "role": "user",
                        "content": user.content[:1000],
                        "filters": user.filters.model_dump(mode="json") if user.filters else None,
                    },
                    {"role": "assistant", "content": message.content[:1000], "filters": None},
                ]
            )
            user = None
    history: list[dict[str, Any]] = []
    for pair in reversed(pairs[-3:]):
        while len(canonical([*pair, *history]).encode("utf-8")) > 4800:
            longest = max(pair, key=lambda item: len(item["content"]))
            if len(longest["content"]) <= 100:
                break
            longest["content"] = longest["content"][: len(longest["content"]) // 2]
        if len(canonical([*pair, *history]).encode("utf-8")) <= 4800:
            history = [*pair, *history]
    return canonical(
        {
            "question": payload.question,
            "history_untrusted": history,
            "history_omitted": len(payload.history) - len(history),
            "memory_untrusted": prompt_memory(payload.memory, payload.memory_consent),
            "reply_preferences": payload.preferences.model_dump() if payload.preferences else None,
            "scope": {
                "filters": plan.filters.model_dump(mode="json"),
                "as_of": tools.as_of,
                "business_date": plan.business_date.isoformat(),
                "timezone": plan.timezone,
            },
            "answer_mode": payload.preferences.length
            if payload.preferences
            else payload.answer_mode,
        }
    )


def finalize_answer(
    answer: str, sources: dict[int, dict[str, Any]], question: str
) -> dict[str, Any]:
    if not answer.strip() or len(answer) > 12000 or re.search(r"https?://", answer, re.I):
        raise ResearchRejected("INVALID_CITATIONS")
    indices = list(dict.fromkeys(int(value) for value in re.findall(r"\[(\d+)\]", answer)))
    if any(index not in sources for index in indices):
        raise ResearchRejected("INVALID_CITATIONS")
    if re.search(r"\[[0-9a-f]{8}-[0-9a-f-]{27,}\]", answer, re.I):
        raise ResearchRejected("INVALID_CITATIONS")
    if not indices:
        if re.fullmatch(
            r"\s*(hi|hello|hey|你好|您好|嗨|谢谢|thanks|thank you)[!！。.\s]*", question, re.I
        ):
            return {"answer": answer, "citations": [], "answer_status": "answered"}
        return {
            "answer": "当前研究未取得足够的可核查依据，请调整日期、分类或事件范围后再问。",
            "citations": [],
            "answer_status": "no_answer",
        }
    return {
        "answer": answer,
        "citations": [sources[index] for index in indices],
        "answer_status": "answered",
    }


async def research_answer_stream(
    run: PublicRun,
    plan: QueryPlan,
    repository: PostgresRepository,
    settings: Settings,
    policy: ResearchPolicy,
    registry: ResearchSessions,
    runtime: httpx.AsyncClient,
    *,
    provider_transport: httpx.AsyncBaseTransport | None = None,
    sandbox: SandboxClient | None = None,
    artifacts: ArtifactStore | None = None,
) -> AsyncGenerator[bytes, None]:
    guard = ResearchGuard(
        run.reservation.id,
        run.owner,
        run.reservation.deadline,
        python_enabled=policy.contract["python"]["enabled"],
    )
    provider = ResearchModelStream(
        settings.llm_api_key or "",
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        transport=provider_transport
        or PublicAsyncTransport(resolver=configured_resolver(settings.fetch_dns_mode)),
    )
    turn = 0
    seq = 0
    draft = ""
    result = None
    try:
        async with research_scope(repository, guard, plan.filters, policy.skills) as tools:
            if guard.python_enabled:
                if sandbox is None or artifacts is None:
                    raise ResearchRejected("SANDBOX_UNAVAILABLE")
                tools.attach_python(sandbox, artifacts)
            total = await tools._count()
            yield sse(
                "meta",
                {
                    "request_id": str(plan.request_id),
                    "protocol_version": 2,
                    "run_id": str(guard.run_id),
                    "query_plan_public": plan.model_dump(mode="json"),
                    "data_mode": "postgres",
                    "as_of": tools.as_of,
                    "filters_applied": plan.filters.model_dump(mode="json"),
                },
            )
            if total == 0:
                yield sse(
                    "reset",
                    {"turn": 1, "text": "当前范围内没有匹配事件，请调整日期、分类或关键词后再问。"},
                )
                yield sse("sources", {"items": []})
                yield sse(
                    "done",
                    {
                        "status": "completed",
                        "answer_status": "no_answer",
                        "scope_total": 0,
                        "retrieved_count": 0,
                        "summarized_count": 0,
                        "citation_count": 0,
                        "coverage": "none",
                    },
                )
                return
            prompt = make_research_prompt(run.payload, plan, tools)
            session = ResearchSession(
                guard=guard,
                system=policy.system + "\n\n" + ANSWER_CONTRACT,
                prompt=prompt,
                provider=provider,
                executor=tools,
                ledger=PostgresResearchLedger(
                    run.quota.sessions,
                    run.owner,
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                ),
            )
            async with registry.register(session):
                events = runtime_events(runtime, prompt, settings.llm_max_tokens, guard.capability)
                async with aclosing(events):
                    async for event in events:
                        kind = event["type"]
                        if kind == "turn":
                            next_turn = event.get("turn")
                            if type(next_turn) is not int or next_turn != turn + 1 or next_turn > 3:
                                raise ResearchRejected("INVALID_MODEL_STREAM")
                            turn, draft, seq = next_turn, "", 0
                            yield sse("reset", {"turn": turn, "text": ""})
                            yield sse(
                                "status", {"phase": "researching", "message": "正在检索与核查依据"}
                            )
                        elif kind == "text":
                            value = event.get("text")
                            if (
                                event.get("turn") != turn
                                or not isinstance(value, str)
                                or len(draft) + len(value) > 12000
                            ):
                                raise ResearchRejected("INVALID_MODEL_STREAM")
                            draft += value
                            seq += 1
                            yield sse("token", {"seq": seq, "turn": turn, "text": value})
                        elif kind == "tool":
                            yield sse(
                                "status",
                                {"phase": "researching", "message": "正在核查本轮数据与来源"},
                            )
                        else:
                            result = event
            if not result or result.get("status") != "completed" or result.get("answer") != draft:
                raise ResearchRejected("RESEARCH_INCOMPLETE")
            final = finalize_answer(draft, tools.sources, run.payload.question)
            if final["answer"] != draft:
                yield sse("reset", {"turn": turn, "text": final["answer"]})
            sources = final["citations"]
            event_ids = {
                source.get("event_id") or source.get("article_id")
                for source in sources if source.get("kind") in {"evidence", "article"}
            }
            cited_indices = {source["index"] for source in sources}
            yield sse("sources", {"items": sources})
            if guard.python_enabled:
                yield sse(
                    "artifacts",
                    {
                        "run_id": str(guard.run_id),
                        "items": [
                            item
                            for item in tools.artifacts
                            if item["citation_index"] in cited_indices
                        ],
                    },
                )
            yield sse(
                "done",
                {
                    "status": "completed",
                    "answer_status": final["answer_status"],
                    "scope_total": total,
                    "retrieved_count": len(tools.retrieved_events),
                    "summarized_count": len(event_ids),
                    "citation_count": len(sources),
                    "coverage": "complete" if len(event_ids) == total else "partial",
                    "dataset_citation_count": sum(
                        source.get("kind") == "dataset" for source in sources
                    ),
                },
            )
    except (asyncio.CancelledError, GeneratorExit):
        raise
    except Exception:
        yield sse(
            "error",
            {
                "code": "RESEARCH_INCOMPLETE",
                "message": "研究未完成，当前内容仅为草稿。",
                "retryable": False,
                "request_id": str(plan.request_id),
            },
        )
        yield sse("sources", {"items": []})
        yield sse("done", {"status": "failed"})
    finally:
        guard.close()
        await provider.close()
