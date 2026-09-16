"""Opt-in Linux: production ask routes -> pi -> PostgreSQL -> real gVisor -> downloads.

Only the paid provider is scripted. Policy activation is confined to a temporary
copy and private loopback test processes. Never modifies the packaged policy or
running application. Uses the existing disposable radar_test_ database fixture.
"""

import asyncio
import json
import os
import secrets
import shutil
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from sqlalchemy import select
from test_research_public_postgres import Chunks, event
from test_research_tools import data  # noqa: F401

from radar import main
from radar.config import Settings
from radar.public_assistant import router as public_router
from radar.public_identity import PublicIdentity
from radar.public_quota import PostgresPublicQuota, PublicAskRow, QuotaPolicy
from radar.qa_limits import AskAdmission
from radar.research_artifacts import ArtifactStore
from radar.research_artifacts import router as artifact_router
from radar.research_http import ResearchSessions, research_router
from radar.research_ledger import ResearchCallRow
from radar.research_policy import ResearchPolicy

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        sys.platform != "linux" or os.environ.get("RADAR_RUN_GVISOR_TESTS") != "1",
        reason="requires explicit Linux gVisor acceptance opt-in",
    ),
]
ROOT = Path(__file__).resolve().parents[3]
IMAGE = "sha256:7a72dfb14070c165eeba7eb388220b1462181225f96e8720e29ec1a0268b5021"
CODE = """import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
frame = pd.DataFrame(datasets[0]['rows'])
total = int(frame['count'].sum())
Path(output_dir, 'summary.json').write_text(json.dumps({'total': total}))
frame.to_csv(Path(output_dir, 'counts.csv'), index=False)
fig, axis = plt.subplots(figsize=(3, 2))
axis.bar(frame['category'], frame['count'])
fig.savefig(Path(output_dir, 'counts.png'))
plt.close(fig)
print(total)
"""


async def tasks():
    child = await asyncio.create_subprocess_exec(
        "docker",
        "ps",
        "--all",
        "--filter",
        "label=ai-radar.sandbox=task",
        "--format",
        "{{.ID}}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    raw, _ = await asyncio.wait_for(child.communicate(), 5)
    assert child.returncode == 0
    return raw.strip()


async def stop(child):
    if child is not None and child.returncode is None:
        child.terminate()
        try:
            await asyncio.wait_for(child.wait(), 8)
        except TimeoutError:
            child.kill()
            await child.wait()


async def ready(client, address, process, headers=None):
    async with asyncio.timeout(35):
        while True:
            assert process.returncode is None, "private process exited during startup"
            try:
                response = await client.get(address + "/health", headers=headers)
                if response.status_code == 200:
                    return response.json()
            except httpx.ConnectError:
                pass
            await asyncio.sleep(0.05)


def frames(response):
    assert response.status_code == 200, response.text
    return [
        (block.split("\n")[0][7:], json.loads(block.split("\ndata: ")[1]))
        for block in response.text.strip().split("\n\n")
    ]


async def test_public_python_chain(data, monkeypatch, tmp_path):  # noqa: F811
    import radar.research_endpoints as endpoints

    repository, filters, _, _, _, _, _, _ = data
    node = shutil.which("node")
    assert node, "Node and the compiled pi runtime are required"
    assert not await tasks(), "refuse to overlap existing sandbox tasks"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8092))  # Refuse to touch an existing controller.
    sock, runtime_sock = socket.socket(), socket.socket()
    sock.bind(("127.0.0.1", 0))
    runtime_sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    runtime_port = runtime_sock.getsockname()[1]
    runtime_sock.close()
    policy_root = tmp_path / "policy"
    shutil.copytree(ROOT / "agent/research", policy_root)
    contract = json.loads((policy_root / "policy.json").read_text())
    assert contract["python"]["enabled"] is False
    contract["python"]["enabled"] = True
    (policy_root / "policy.json").write_text(json.dumps(contract))
    policy = ResearchPolicy.load(policy_root)
    runtime_token, sandbox_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    token_file = tmp_path / "sandbox-token"
    token_file.write_text(sandbox_token)
    token_file.chmod(0o600)
    settings = Settings(
        research_agent_enabled=True,
        radar_data_mode="postgres",
        llm_api_key="fixture-key",
        research_runtime_token=runtime_token,
        research_runtime_url=f"http://127.0.0.1:{runtime_port}",
        sandbox_controller_token=sandbox_token,
        sandbox_image_id=IMAGE,
    )
    app = FastAPI()
    app.state.settings = settings
    app.state.repository = repository
    app.state.research_policy = policy
    app.state.research_sessions = ResearchSessions()
    app.state.public_identity = PublicIdentity(secrets.token_hex(32))
    app.state.public_quota = PostgresPublicQuota(
        repository.sessions, QuotaPolicy(input_per_day=10000000, output_per_day=10000000)
    )
    app.state.ask_admission = AskAdmission()
    artifact_clock = [time.monotonic()]
    app.state.research_artifacts = ArtifactStore(clock=lambda: artifact_clock[0])
    app.include_router(public_router)
    app.include_router(research_router(app.state.research_sessions))
    app.include_router(artifact_router)
    # Register the actual production functions, including real query planning.
    app.add_api_route("/api/v1/ask/stream", main.ask_stream, methods=["POST"])
    app.add_api_route("/api/v1/ask", main.ask, methods=["POST"])
    app.dependency_overrides[main.get_clock] = lambda: datetime(2026, 9, 16, tzinfo=UTC)
    monkeypatch.setattr(endpoints, "effective_model_settings", lambda _: settings)
    calls, datasets = [], []
    mode = "success"

    def provider(request):
        body = json.loads(request.content)
        calls.append(body)
        assert "fixture-key" not in request.content.decode()
        assert sandbox_token not in request.content.decode()
        assert "outside-authorized-scope" not in request.content.decode()
        previous = [item for item in body["messages"] if item["role"] == "tool"]
        if not previous:
            name, args = "aggregate_events", {"dimension": "category"}
        elif len(previous) == 1:
            dataset = json.loads(previous[-1]["content"])
            assert dataset["total_events"] == 10
            assert sum(row["count"] for row in dataset["rows"]) == 10
            datasets.append(dataset)
            name, args = (
                "run_python",
                {
                    "code": CODE,
                    "dataset_ids": [str(uuid4()) if mode == "foreign" else dataset["dataset_id"]],
                },
            )
        else:
            analysis = json.loads(previous[-1]["content"])
            assert analysis["stdout"].strip() == "10"
            assert len(analysis["artifacts"]) == 3
            index = 99 if mode == "invalid_citation" else analysis["citation_index"]
            return httpx.Response(
                200,
                stream=Chunks(
                    [
                        event({"content": "当前范围十条事件，Python 汇总结果为 10"}),
                        event(
                            {"content": f"[{index}]。"},
                            "stop",
                            usage={
                                "prompt_tokens": 40,
                                "completion_tokens": 9,
                                "total_tokens": 49,
                            },
                        ),
                        b"data: [DONE]\n\n",
                    ]
                ),
            )
        return httpx.Response(
            200,
            stream=Chunks(
                [
                    event(
                        {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": f"step-{len(previous)}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(args)},
                                }
                            ]
                        },
                        "tool_calls",
                        usage={
                            "prompt_tokens": 30,
                            "completion_tokens": 7,
                            "total_tokens": 37,
                        },
                    ),
                    b"data: [DONE]\n\n",
                ]
            ),
        )

    app.state.answer_stream_transport = httpx.MockTransport(provider)
    environment = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8"}
    controller = runtime = task = None
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    try:
        controller = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "radar.sandbox_controller",
            cwd=ROOT,
            env={
                **environment,
                "PYTHONPATH": str(ROOT / "backend/src"),
                "RADAR_SANDBOX_TOKEN_FILE": str(token_file),
                "RADAR_SANDBOX_IMAGE_ID": IMAGE,
            },
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        task = asyncio.create_task(server.serve(sockets=[sock]))
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(0.01)
        # Explicit fixture boot loads the temporary policy, never edits packaged rules.
        compiled = ROOT / "agent/runtime/dist/src"
        boot = "\n".join(
            [
                f"import {{loadPolicy}} from {json.dumps((compiled / 'policy.js').as_uri())};",
                "import {createRuntimeServer} from "
                f"{json.dumps((compiled / 'server.js').as_uri())};",
                f"import {{httpBroker}} from {json.dumps((compiled / 'broker.js').as_uri())};",
                f"const p = await loadPolicy(new URL({json.dumps(policy_root.as_uri() + '/')}));",
                "createRuntimeServer({token:process.env.RADAR_RUNTIME_TOKEN,system:p.system,",
                "policyDigest:p.digest,pythonEnabled:p.pythonEnabled,",
                "broker:c=>httpBroker(process.env.RADAR_BROKER_ORIGIN,c)})",
                ".listen(Number(process.env.PORT),'127.0.0.1');",
            ]
        )
        runtime = await asyncio.create_subprocess_exec(
            node,
            "--input-type=module",
            "-e",
            boot,
            cwd=ROOT,
            env={
                **environment,
                "RADAR_RUNTIME_TOKEN": runtime_token,
                "RADAR_BROKER_ORIGIN": base,
                "PORT": str(runtime_port),
            },
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        async with httpx.AsyncClient(base_url=base, timeout=40, trust_env=False) as client:
            await ready(
                client,
                "http://127.0.0.1:8092",
                controller,
                {"Authorization": "Bearer " + sandbox_token},
            )
            health = await ready(client, f"http://127.0.0.1:{runtime_port}", runtime)
            assert health["python"] is True and health["policy_digest"] == policy.digest

            async def quota():
                return (await client.get("/api/v1/assistant/session")).json()["quota"]["remaining"]

            def question(**extra):
                return {
                    "question": "统计分类",
                    "filters": filters.model_dump(mode="json"),
                    "client_request_id": str(uuid4()),
                    **extra,
                }

            assert await quota() == 5
            first = question()
            response = await client.post("/api/v1/ask/stream", json=first)
            stream = frames(response)
            assert stream[-1][1]["status"] == "completed", response.text
            assert [v["turn"] for k, v in stream if k == "reset"] == [1, 2, 3]
            sources = next(v["items"] for k, v in stream if k == "sources")
            analysis = next(item for item in sources if item["kind"] == "analysis")
            assert analysis["analysis"]["code"] == CODE
            artifacts = next(v["items"] for k, v in stream if k == "artifacts")
            assert len(artifacts) == 3
            assert len(calls) == 3 and await quota() == 4
            assert (await client.post("/api/v1/ask", json=first)).status_code == 409
            assert len(calls) == 3 and await quota() == 4
            for item in artifacts:
                assert item["citation_index"] == analysis["index"]
                download = await client.get(item["download_url"])
                assert download.status_code == 200
                assert download.headers["cache-control"] == "no-store"
                assert download.headers["x-content-type-options"] == "nosniff"
                if item["name"] == "summary.json":
                    assert download.json() == {"total": 10}
                elif item["name"] == "counts.csv":
                    assert "model_release,8" in download.text and "product,2" in download.text
                else:
                    assert item["name"] == "counts.png" and download.content.startswith(b"\x89PNG")
                async with httpx.AsyncClient(base_url=base, trust_env=False) as other:
                    await other.get("/api/v1/assistant/session")
                    assert (await other.get(item["download_url"])).status_code == 404
            assert not await tasks()
            # Same browser follow-up counts as a second question, with a fresh dataset.
            second = await client.post(
                "/api/v1/ask",
                json=question(
                    history=[
                        {"role": "user", "content": "统计分类"},
                        {"role": "assistant", "content": "之前统计为十条[2]。"},
                    ]
                ),
            )
            assert second.status_code == 200, second.text
            assert second.json()["status"] == "completed" and len(second.json()["artifacts"]) == 3
            assert datasets[0]["dataset_id"] != datasets[1]["dataset_id"]
            assert await quota() == 3 and len(calls) == 6
            mode = "invalid_citation"
            failed = frames(await client.post("/api/v1/ask/stream", json=question()))
            assert failed[-1] == ("done", {"status": "failed"})
            assert ("sources", {"items": []}) in failed
            assert not any(k == "artifacts" for k, _ in failed)
            assert await quota() == 2 and not await tasks()
            mode = "foreign"
            failed = frames(await client.post("/api/v1/ask/stream", json=question()))
            assert failed[-1] == ("done", {"status": "failed"})
            assert not any(k == "artifacts" for k, _ in failed)
            assert await quota() == 1 and not await tasks()
            artifact_clock[0] += 901
            assert (await client.get(artifacts[0]["download_url"])).status_code == 404
            # Controller unavailable must reject before a fifth quota charge/model call.
            await stop(controller)
            before = len(calls)
            assert (await client.post("/api/v1/ask/stream", json=question())).status_code == 503
            assert await quota() == 1 and len(calls) == before
            async with repository.sessions() as session:
                parents = list(
                    (
                        await session.scalars(
                            select(PublicAskRow).where(
                                PublicAskRow.ip_hash
                                == app.state.public_identity.ip_key("127.0.0.1")
                            )
                        )
                    ).all()
                )
                assert len(parents) == 4 and all(item.charged for item in parents)
                recorded = list(
                    (
                        await session.scalars(
                            select(ResearchCallRow).where(
                                ResearchCallRow.run_id.in_([item.id for item in parents])
                            )
                        )
                    ).all()
                )
                assert len(recorded) == len(calls)
            for secret in (sandbox_token, runtime_token, "fixture-key"):
                assert secret not in response.text and secret not in second.text
    finally:
        await stop(runtime)
        await stop(controller)
        if task is not None:
            server.should_exit = True
            await asyncio.wait_for(task, 8)
        sock.close()
        token_file.unlink(missing_ok=True)
    assert not await tasks()
    assert (
        json.loads((ROOT / "agent/research/policy.json").read_text())["python"]["enabled"] is False
    )
