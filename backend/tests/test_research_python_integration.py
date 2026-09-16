import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest

from radar.config import Settings
from radar.qa_service import QaError
from radar.research_artifacts import ArtifactStore
from radar.research_gateway import provider_tools
from radar.research_guard import RequestedTool, ResearchGuard, ResearchRejected
from radar.research_policy import ResearchPolicy
from radar.research_service import research_preflight
from radar.research_tools import ResearchTools
from radar.sandbox_client import SandboxClient
from radar.sandbox_protocol import SandboxArtifact, SandboxResult
from radar.schemas import Filters

ROOT = Path(__file__).resolve().parents[2] / "agent/research"


def python_policy(tmp_path):
    shutil.copytree(ROOT, tmp_path / "pack")
    path = tmp_path / "pack/policy.json"
    policy = json.loads(path.read_text())
    policy["python"]["enabled"] = True
    path.write_text(json.dumps(policy))
    return ResearchPolicy.load(path.parent)


async def test_python_counts_against_both_budgets_and_is_disabled_by_default():
    for enabled in (False, True):
        guard = ResearchGuard(
            uuid4(), "a" * 64, datetime.now(UTC) + timedelta(seconds=90), python_enabled=enabled
        )
        lease = await guard.reserve_model(guard.capability, 1, {}, 100)
        await guard.settle_model(
            guard.capability,
            lease,
            input_tokens=1,
            output_tokens=1,
            requested_tools={
                "a": RequestedTool("run_python", {}),
                "b": RequestedTool("run_python", {}),
            },
        )
        if enabled:
            await guard.begin_tool(guard.capability, "a", "run_python", {})
            await guard.finish_tool("a")
            with pytest.raises(ResearchRejected, match="BUDGET_EXCEEDED"):
                await guard.begin_tool(guard.capability, "b", "run_python", {})
            assert guard.business_calls == guard.python_calls == 1
        else:
            with pytest.raises(ResearchRejected, match="TOOL_UNAVAILABLE"):
                await guard.begin_tool(guard.capability, "a", "run_python", {})
            assert guard.business_calls == guard.python_calls == 0


def test_python_policy_loads_analysis_skill_but_default_schema_omits_execution(tmp_path):
    policy = python_policy(tmp_path)
    assert "analyze-dataset" in policy.skills
    assert "run_python" not in {tool["function"]["name"] for tool in provider_tools()}
    assert "run_python" in {
        tool["function"]["name"] for tool in provider_tools(python_enabled=True)
    }


async def test_tools_attach_analysis_citation_and_dataset_provenance():
    guard = ResearchGuard(
        uuid4(), "a" * 64, datetime.now(UTC) + timedelta(seconds=90), python_enabled=True
    )
    repository = Mock(timezone="Asia/Shanghai")
    tools = ResearchTools(repository, Mock(), guard, Filters(), {}, "2026-09-16", "snapshot")
    dataset = tools._dataset([{"category": "research", "count": 3}], ["category", "count"])
    client = AsyncMock()
    client.run.return_value = SandboxResult(
        "sum=3", (SandboxArtifact("sum.json", "application/json", b"3"),)
    )
    store = ArtifactStore()
    tools.attach_python(client, store)
    result = await tools.execute(
        "run_python", {"code": "print(3)", "dataset_ids": [dataset["dataset_id"]]}
    )
    assert result["citation_index"] == 2
    assert tools.sources[2]["kind"] == "analysis"
    assert tools.sources[2]["input_citation_indices"] == [1]
    assert tools.sources[2]["analysis"]["stdout"] == "sum=3"
    assert tools.artifacts[0]["citation_index"] == 2
    assert tools.artifacts[0]["dataset_ids"] == [dataset["dataset_id"]]
    assert tools.artifacts[0]["data_revision"] == "snapshot"


@pytest.mark.parametrize("failure", ["missing", "wrong-image", "watchdog", "runtime"])
async def test_python_preflight_rejects_unverified_sandbox(tmp_path, failure):
    from test_research_public import plan

    policy = python_policy(tmp_path)
    image = "sha256:" + "a" * 64
    health = {
        "status": "ready",
        "runtime": "gvisor",
        "image_id": image,
        "runsc_sha256": "3e0df2fa28f6ff5430b004f92573b81b75f442f78c780e0c85fdf6c2d572817a",
        "watchdog": "ready",
    }
    if failure == "wrong-image":
        health["image_id"] = "sha256:" + "b" * 64
    if failure == "watchdog":
        health["watchdog"] = "stale"
    if failure == "runtime":
        health["runtime"] = "runc"

    def handler(request):
        if request.url.host == "pi":
            return httpx.Response(
                200, json={"status": "ready", "python": True, "policy_digest": policy.digest}
            )
        return httpx.Response(200, json=health)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://pi"
    ) as http:
        client = SandboxClient(http, "http://127.0.0.1:8092", "x" * 43)
        with pytest.raises(QaError, match="研究服务暂不可用"):
            await research_preflight(
                http,
                plan(),
                Settings(llm_api_key="fake", sandbox_image_id=image),
                policy,
                sandbox=None if failure == "missing" else client,
            )


async def test_python_preflight_accepts_matching_policy_and_attested_controller(tmp_path):
    from test_research_public import plan

    policy = python_policy(tmp_path)
    image = "sha256:" + "a" * 64
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "status": "ready",
                "runtime": "gvisor",
                "python": True,
                "image_id": image,
                "policy_digest": policy.digest,
                "runsc_sha256": "3e0df2fa28f6ff5430b004f92573b81b75f442f78c780e0c85fdf6c2d572817a",
                "watchdog": "ready",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://pi",
        headers={"Authorization": "Bearer pi-token"},
    ) as http:
        client = SandboxClient(http, "http://127.0.0.1:8092", "x" * 43)
        await research_preflight(
            http,
            plan(),
            Settings(llm_api_key="fake", sandbox_image_id=image),
            policy,
            sandbox=client,
        )
    assert calls[1].headers["authorization"] == "Bearer " + "x" * 43
    assert len(calls) == 2
