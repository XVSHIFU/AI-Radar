import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from test_research_public import frames, plan
from test_research_python_integration import python_policy
from test_research_stream import Chunks

from radar.config import Settings
from radar.research_artifacts import ArtifactStore
from radar.research_http import ResearchSessions
from radar.research_service import research_answer_stream
from radar.research_tools import ResearchTools
from radar.sandbox_client import SandboxClient
from radar.sandbox_http import controller_app
from radar.sandbox_protocol import SandboxArtifact, SandboxResult
from radar.schemas import AskRequest


@pytest.mark.parametrize("invalid_citation", [False, True])
async def test_three_model_turns_execute_owned_python_and_publish_only_cited_artifacts(
    tmp_path, monkeypatch, invalid_citation
):
    import radar.research_service as service

    policy = python_policy(tmp_path)
    registry = ResearchSessions()
    artifacts = ArtifactStore()
    calls = []
    executed = []

    @asynccontextmanager
    async def scope(repository, guard, filters, skills):
        tools = ResearchTools(
            Mock(timezone="Asia/Shanghai"), Mock(), guard, filters, skills, "2026-09-16", "frozen"
        )
        tools._count = AsyncMock(return_value=3)

        async def aggregate(args):
            return tools._dataset([{"category": "research", "count": 3}], ["category", "count"])

        tools._aggregate = aggregate
        try:
            yield tools
        finally:
            tools._closed = True
            tools._datasets.clear()

    def provider(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            name, args = "aggregate_events", {"dimension": "category"}
        elif len(calls) == 2:
            data = json.loads(body["messages"][-1]["content"])
            name, args = "run_python", {"code": "print(3)", "dataset_ids": [data["dataset_id"]]}
        else:
            result = json.loads(body["messages"][-1]["content"])
            assert result["stdout"] == "3"
            assert body.get("tools", []) == []
            name, args = None, None
        delta = (
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call-" + str(len(calls)),
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ]
            }
            if name
            else {"content": "计算结果为三[99]。" if invalid_citation else "计算结果为三[2]。"}
        )
        chunk = {
            "choices": [
                {"index": 0, "delta": delta, "finish_reason": "tool_calls" if name else "stop"}
            ],
            "usage": {"prompt_tokens": 40, "completion_tokens": 15, "total_tokens": 55},
        }
        return httpx.Response(
            200,
            stream=Chunks([b"data: " + json.dumps(chunk).encode() + b"\n\n", b"data: [DONE]\n\n"]),
        )

    class Executor:
        async def run(self, code, datasets):
            executed.append((code, datasets))
            return SandboxResult("3", (SandboxArtifact("sum.json", "application/json", b"3"),))

    async def runtime_events(client, prompt, max_output, capability):
        session = next(iter(registry._sessions.values()))
        draft = ""
        for turn in range(1, 4):
            yield {"type": "turn", "turn": turn}
            requested = []
            async for event in session.model(capability, turn, max_output):
                if event["type"] == "tool":
                    requested.append(event)
                elif event["type"] == "text":
                    draft += event["text"]
                    yield {**event, "turn": turn}
            for event in requested:
                await session.tool(capability, event["name"], event["arguments"], event["id"])
                yield {"type": "tool", "name": event["name"], "phase": "finished"}
        yield {"type": "result", "status": "completed", "answer": draft}

    monkeypatch.setattr(service, "research_scope", scope)
    monkeypatch.setattr(service, "runtime_events", runtime_events)
    monkeypatch.setattr(service, "PostgresResearchLedger", lambda *args, **kwargs: AsyncMock())
    run = SimpleNamespace(
        reservation=SimpleNamespace(id=uuid4(), deadline=datetime.now(UTC) + timedelta(seconds=90)),
        owner="a" * 64,
        quota=SimpleNamespace(sessions=None),
        payload=AskRequest(question="计算", client_request_id="test"),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(Executor(), "x" * 43))
    ) as http:
        sandbox = SandboxClient(http, "http://127.0.0.1:8092", "x" * 43)
        result = frames(
            [
                frame
                async for frame in research_answer_stream(
                    run,
                    plan(),
                    None,
                    Settings(llm_api_key="fixture"),
                    policy,
                    registry,
                    http,
                    provider_transport=httpx.MockTransport(provider),
                    sandbox=sandbox,
                    artifacts=artifacts,
                )
            ]
        )
    assert len(calls) == 3 and len(executed) == 1
    if invalid_citation:
        assert result[-1] == ("done", {"status": "failed"})
        assert not any(kind == "artifacts" for kind, _ in result)
    else:
        source = next(data["items"][0] for kind, data in result if kind == "sources")
        assert source["kind"] == "analysis" and source["analysis"]["code"] == "print(3)"
        files = next(data["items"] for kind, data in result if kind == "artifacts")
        assert len(files) == 1 and files[0]["citation_index"] == source["index"] == 2
        assert files[0]["run_id"] == str(run.reservation.id)
        assert result[-1][1]["status"] == "completed"
