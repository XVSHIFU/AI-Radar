import json
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

from radar.config import Settings
from radar.qa_service import QaService
from radar.qa_stream_service import StreamContext, stream_answer
from radar.schemas import AskRequest, Category, Event, Evidence, Filters, QueryPlan


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def upstream(body):
    return b"data: " + json.dumps(body).encode() + b"\n\n"


def context():
    eid = UUID(int=1)
    event = Event(
        id=eid,
        title_zh="事件",
        summary_zh="摘要",
        category=Category.PRODUCT,
        importance=3,
        event_date=date(2026, 9, 15),
        date_precision="day",
        source_count=1,
        evidence_count=1,
        entities=[],
        content_version=1,
    )
    evidence = Evidence(
        id=UUID(int=2),
        event_id=eid,
        article_version_id=UUID(int=3),
        paragraph_id="p1",
        quote_text="冻结原文",
        source_url="https://source.example/a",
        title="来源",
        verification_status="unverified",
        source_published_at=datetime(2026, 9, 15, tzinfo=UTC),
        event_date=date(2026, 9, 15),
    )
    payload = AskRequest(question="总结", client_request_id="stream-1")
    plan = QueryPlan(
        intent="structured_summary",
        filters=Filters(),
        timezone="Asia/Shanghai",
        business_date=date(2026, 9, 15),
        date_until_exclusive=None,
        constraints_origin={},
        free_text="",
        requires_clarification=False,
        clarification_candidates=[],
        warnings=[],
        data_mode="postgres",
        request_id="request-1",
    )
    base = {
        "request_id": "request-1",
        "scope_total": 1,
        "retrieved_count": 1,
        "coverage": "complete",
        "query_plan_public": plan.model_dump(mode="json"),
        "data_mode": "postgres",
        "as_of": datetime(2026, 9, 15, tzinfo=UTC),
        "filters_applied": {},
    }
    return StreamContext(payload, plan, [event], [(event, evidence)], "prompt", base, UUID(int=4))


def settings():
    return Settings(llm_api_key="secret", llm_base_url="https://api.deepseek.com/v1")


async def resolver(host):
    return ["93.184.216.34"]


def decode(chunks):
    text = b"".join(chunks).decode()
    out = []
    for frame in text.strip().split("\n\n"):
        lines = frame.splitlines()
        out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out


@pytest.mark.asyncio
async def test_answer_stream_emits_real_deltas_then_database_sources(monkeypatch):
    mark = AsyncMock()
    monkeypatch.setattr(QaService, "mark", mark)
    chunks = [
        upstream({"id": "r", "choices": [{"delta": {"content": "结论"}, "finish_reason": None}]}),
        upstream({"id": "r", "choices": [{"delta": {"content": "[1]"}, "finish_reason": "stop"}]}),
        upstream(
            {
                "id": "r",
                "choices": [],
                "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10},
            }
        ),
        b"data: [DONE]\n\n",
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks)))
    frames = decode(
        [x async for x in stream_answer(context(), None, settings(), resolver, transport=transport)]
    )  # type: ignore[arg-type]
    assert [name for name, _ in frames] == ["meta", "status", "token", "token", "sources", "done"]
    assert frames[2][1]["text"] == "结论" and frames[3][1]["text"] == "[1]"
    assert frames[4][1]["items"][0]["quote_text"] == "冻结原文"
    assert frames[-1][1]["status"] == "completed" and frames[-1][1]["coverage"] == "complete"
    assert (
        mark.await_args.args[1] == "completed" and mark.await_args.args[2].usage.total_tokens == 10
    )


@pytest.mark.asyncio
async def test_failure_after_token_never_marks_partial_draft_success(monkeypatch):
    mark = AsyncMock()
    monkeypatch.setattr(QaService, "mark", mark)
    chunks = [
        upstream({"id": "r", "choices": [{"delta": {"content": "草稿"}, "finish_reason": None}]})
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks)))
    frames = decode(
        [x async for x in stream_answer(context(), None, settings(), resolver, transport=transport)]
    )  # type: ignore[arg-type]
    assert [name for name, _ in frames][-3:] == ["error", "sources", "done"]
    assert frames[-1][1]["status"] == "failed" and frames[-1][1]["answer_status"] is None
    assert mark.await_args.args[1] == "unknown"


@pytest.mark.asyncio
async def test_client_disconnect_closes_generator_and_marks_unknown(monkeypatch):
    mark = AsyncMock()
    monkeypatch.setattr(QaService, "mark", mark)
    chunks = [
        upstream({"id": "r", "choices": [{"delta": {"content": "草稿"}, "finish_reason": None}]}),
        b"data: [DONE]\n\n",
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks)))
    stream = stream_answer(context(), None, settings(), resolver, transport=transport)  # type: ignore[arg-type]
    await anext(stream)
    await anext(stream)
    await anext(stream)
    await stream.aclose()
    assert (
        mark.await_args.args[1] == "unknown"
        and mark.await_args.args[3] == "cancelled_outcome_unknown"
    )


@pytest.mark.asyncio
async def test_streaming_answer_limit_fails_without_emitting_oversized_token(monkeypatch):
    mark = AsyncMock()
    monkeypatch.setattr(QaService, "mark", mark)
    chunks = [
        upstream(
            {"id": "r", "choices": [{"delta": {"content": "x" * 12001}, "finish_reason": None}]}
        ),
        upstream({"id": "r", "choices": [{"delta": {}, "finish_reason": "stop"}]}),
        b"data: [DONE]\n\n",
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks)))
    frames = decode(
        [
            item
            async for item in stream_answer(
                context(), None, settings(), resolver, transport=transport
            )
        ]
    )  # type: ignore[arg-type]
    assert "token" not in [name for name, _body in frames]
    assert frames[-1][1]["status"] == "failed"
    assert mark.await_args.args[1] == "failed"
