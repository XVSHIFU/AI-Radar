"""Actual public HTTP -> pi -> capability gateway -> PostgreSQL -> cited SSE.

Only the upstream paid provider is a fixture. Never runs on the business database.
"""

import asyncio
import json
import os
import shutil
import socket
from datetime import date
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from sqlalchemy import select
from test_research_tools import data  # noqa: F401

from radar.config import Settings
from radar.models import LlmCallRow
from radar.public_assistant import router as public_router
from radar.public_identity import PublicIdentity
from radar.public_quota import PostgresPublicQuota, PublicAskRow, QuotaPolicy
from radar.qa_limits import AskAdmission
from radar.research_endpoints import public_research_response
from radar.research_http import ResearchSessions, research_router
from radar.research_ledger import ResearchCallRow
from radar.research_policy import ResearchPolicy
from radar.schemas import AskRequest, QueryPlan

pytestmark = pytest.mark.postgres
ROOT = Path(__file__).resolve().parents[3]


def event(delta=None, finish=None, **extra):
    return (
        b"data: "
        + json.dumps(
            {"choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}], **extra}
        ).encode()
        + b"\n\n"
    )


class Chunks(httpx.AsyncByteStream):
    def __init__(self, blocks):
        self.blocks = blocks

    async def __aiter__(self):
        for block in self.blocks:
            yield block


async def test_public_pi_answers_and_followups_share_durable_question_quota(data, monkeypatch):  # noqa: F811
    import radar.research_endpoints as endpoints

    repository, filters, _, _, _, _, _, _ = data
    node = shutil.which("node")
    assert node, "Compiled pi runtime and Node are required for this integration test"
    sock, runtime_sock = socket.socket(), socket.socket()
    sock.bind(("127.0.0.1", 0))
    runtime_sock.bind(("127.0.0.1", 0))
    runtime_port = runtime_sock.getsockname()[1]
    runtime_sock.close()
    token = "fixture-runtime-" + "a" * 32
    settings = Settings(
        research_agent_enabled=True,
        radar_data_mode="postgres",
        llm_api_key="fixture-provider-key",
        research_runtime_token=token,
        research_runtime_url=f"http://127.0.0.1:{runtime_port}",
    )
    app = FastAPI()
    app.state.settings = settings
    app.state.research_policy = ResearchPolicy.load(ROOT / "agent/research")
    registry = app.state.research_sessions = ResearchSessions()
    app.state.public_identity = PublicIdentity("test-only-" + uuid4().hex)
    app.state.public_quota = PostgresPublicQuota(
        repository.sessions, QuotaPolicy(input_per_day=10000000, output_per_day=10000000)
    )
    app.state.ask_admission = AskAdmission()
    app.include_router(public_router)
    app.include_router(research_router(registry))
    monkeypatch.setattr(endpoints, "effective_model_settings", lambda _: settings)
    paid = []
    invalid = False

    def provider(request):
        body = json.loads(request.content)
        paid.append(body)
        assert body["messages"][0]["role"] == "system"
        if body["messages"][-1]["role"] != "tool":
            blocks = [
                event({"content": "正在统计，暂时还没有结果。"}),
                event(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "aggregate-1",
                                "type": "function",
                                "function": {
                                    "name": "aggregate_events",
                                    "arguments": '{"dimension":"category"}',
                                },
                            }
                        ]
                    },
                    "tool_calls",
                    usage={"prompt_tokens": 30, "completion_tokens": 7, "total_tokens": 37},
                ),
            ]
        else:
            dataset = json.loads(body["messages"][-1]["content"])
            assert dataset["total_events"] == 10
            assert sum(row["count"] for row in dataset["rows"]) == 10
            index = 99 if invalid else dataset["citation_index"]
            blocks = [
                event({"content": "库内共十条事件"}),
                event(
                    {"content": f"[{index}]。"},
                    "stop",
                    usage={"prompt_tokens": 40, "completion_tokens": 9, "total_tokens": 49},
                ),
            ]
        return httpx.Response(200, stream=Chunks([*blocks, b"data: [DONE]\n\n"]))

    app.state.answer_stream_transport = httpx.MockTransport(provider)

    @app.post("/api/v1/ask/stream")
    @app.post("/api/v1/ask")
    async def ask(payload: AskRequest, request: Request):
        query = QueryPlan(
            intent="structured_summary",
            filters=filters,
            timezone="Asia/Shanghai",
            business_date=date(2026, 9, 16),
            date_until_exclusive=None,
            constraints_origin={},
            free_text="",
            requires_clarification=False,
            clarification_candidates=[],
            warnings=[],
            request_id=str(uuid4()),
        )
        return await public_research_response(
            payload, query, request, repository, streaming=request.url.path.endswith("/stream")
        )

    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    process = None
    try:
        async with asyncio.timeout(15):
            while not server.started:
                await asyncio.sleep(0.01)
        environment = {
            key: os.environ[key]
            for key in ("PATH", "SystemRoot", "TEMP", "TMP")
            if key in os.environ
        }
        environment.update(
            RADAR_RUNTIME_TOKEN=token,
            RADAR_BROKER_ORIGIN=f"http://127.0.0.1:{sock.getsockname()[1]}",
            RADAR_RUNTIME_HOST="127.0.0.1",
            PORT=str(runtime_port),
        )
        process = await asyncio.create_subprocess_exec(
            node,
            str(ROOT / "agent/runtime/dist/src/server.js"),
            cwd=ROOT,
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        async with httpx.AsyncClient(timeout=30) as client:
            async with asyncio.timeout(15):
                while True:
                    assert process.returncode is None, "pi exited before readiness"
                    try:
                        if (
                            await client.get(f"http://127.0.0.1:{runtime_port}/health")
                        ).status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    await asyncio.sleep(0.05)
            base = f"http://127.0.0.1:{sock.getsockname()[1]}"
            assert (await client.get(base + "/api/v1/assistant/session")).json()["quota"][
                "remaining"
            ] == 20
            first = {"question": "统计分类", "client_request_id": str(uuid4())}
            response = await client.post(base + "/api/v1/ask/stream", json=first)
            assert response.status_code == 200, response.text
            frames = [
                (block.split("\n")[0][7:], json.loads(block.split("\ndata: ")[1]))
                for block in response.text.strip().split("\n\n")
            ]
            assert frames[-1][1]["status"] == "completed", response.text
            assert [body["turn"] for kind, body in frames if kind == "reset"] == [1, 2]
            source = frames[-2][1]["items"][0]
            assert source["kind"] == "dataset" and source["dataset"]["total_events"] == 10
            assert source["source_url"] == ""
            assert (await client.post(base + "/api/v1/ask", json=first)).status_code == 409
            assert len(paid) == 2
            followup = {
                "question": "再统计一次",
                "client_request_id": str(uuid4()),
                "history": [
                    {"role": "user", "content": "统计分类"},
                    {"role": "assistant", "content": "库内共十条事件[1]。"},
                ],
            }
            response = await client.post(base + "/api/v1/ask", json=followup)
            assert response.status_code == 200, response.text
            assert response.json()["answer"] == "库内共十条事件[1]。"
            assert (await client.get(base + "/api/v1/assistant/session")).json()["quota"][
                "remaining"
            ] == 18
            invalid = True
            response = await client.post(
                base + "/api/v1/ask/stream",
                json={"question": "失败引用", "client_request_id": str(uuid4())},
            )
            assert '"status": "failed"' in response.text, response.text
            assert '"items": []' in response.text
            assert "fixture-provider-key" not in response.text and token not in response.text
            assert len(paid) == 6  # Two model calls still count as one submitted question.
            assert (await client.get(base + "/api/v1/assistant/session")).json()["quota"][
                "remaining"
            ] == 17
        async with repository.sessions() as session:
            parents = list(
                (
                    await session.scalars(
                        select(PublicAskRow).where(
                            PublicAskRow.ip_hash == app.state.public_identity.ip_key("127.0.0.1")
                        )
                    )
                ).all()
            )
            assert len(parents) == 3 and all(p.charged for p in parents)
            assert all((p.input_charge, p.output_charge) == (70, 16) for p in parents)
            calls = list(
                (
                    await session.scalars(
                        select(ResearchCallRow).where(
                            ResearchCallRow.run_id.in_([p.id for p in parents])
                        )
                    )
                ).all()
            )
            assert len(calls) == 6
            usage = list(
                (
                    await session.scalars(
                        select(LlmCallRow).where(
                            LlmCallRow.id.in_([c.model_call_id for c in calls])
                        )
                    )
                ).all()
            )
            assert len(usage) == 6 and all(row.status == "completed" for row in usage)
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5)
        server.should_exit = True
        await asyncio.wait_for(task, timeout=5)
        sock.close()
