import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from radar.research_artifacts import ArtifactStore
from radar.research_guard import ResearchGuard, ResearchRejected
from radar.research_python import ResearchPython
from radar.sandbox_client import SandboxClient
from radar.sandbox_http import controller_app
from radar.sandbox_protocol import SandboxArtifact, SandboxResult


def guard(owner="a" * 64):
    return ResearchGuard(uuid4(), owner, datetime.now(UTC) + timedelta(seconds=90))


def setup():
    run = guard()
    dataset = str(uuid4())
    registry = {dataset: {"dataset_id": dataset, "rows": [{"count": 3}]}}
    client = AsyncMock()
    client.run.return_value = SandboxResult(
        "3", (SandboxArtifact("result.json", "application/json", b"3"),)
    )
    store = ArtifactStore()
    return ResearchPython(run, registry, client, store), dataset, client, store


async def test_unknown_dataset_or_extra_authority_never_reaches_controller():
    tool, dataset, client, _ = setup()
    with pytest.raises(ResearchRejected, match="DATASET_NOT_FOUND"):
        await tool.execute({"code": "print(3)", "dataset_ids": [str(uuid4())]})
    with pytest.raises(ResearchRejected, match="INVALID_ARGUMENT"):
        await tool.execute({"code": "print(3)", "dataset_ids": [dataset], "owner": "b" * 64})
    client.run.assert_not_called()


async def test_owner_run_provenance_and_single_execution():
    tool, dataset, client, store = setup()
    result = await tool.execute({"code": "print(3)", "dataset_ids": [dataset]})
    artifact = next(iter(store._records.values()))
    assert artifact.owner == tool.guard.owner_hash
    assert artifact.run_id == tool.guard.run_id and artifact.dataset_ids == (dataset,)
    assert result["artifacts"][0]["download_url"].endswith(str(artifact.id))
    with pytest.raises(ResearchRejected, match="PYTHON_BUDGET_EXCEEDED"):
        await tool.execute({"code": "print(4)", "dataset_ids": [dataset]})
    client.run.assert_awaited_once()


async def test_failed_task_still_consumes_python_budget():
    tool, dataset, client, store = setup()
    client.run.side_effect = ResearchRejected("EXECUTION_TIMEOUT")
    for code in ("EXECUTION_TIMEOUT", "PYTHON_BUDGET_EXCEEDED"):
        with pytest.raises(ResearchRejected, match=code):
            await tool.execute({"code": "while True: pass", "dataset_ids": [dataset]})
    client.run.assert_awaited_once()
    assert not store._records


async def test_scope_closing_during_execution_does_not_publish_artifact():
    tool, dataset, client, store = setup()
    output = client.run.return_value

    async def execute(*args):
        tool.guard.close()
        return output

    client.run.side_effect = execute
    with pytest.raises(ResearchRejected):
        await tool.execute({"code": "print(3)", "dataset_ids": [dataset]})
    assert not store._records


async def test_simultaneous_python_requests_only_execute_once():
    tool, dataset, client, store = setup()
    entered = asyncio.Event()
    resume = asyncio.Event()
    output = client.run.return_value

    async def execute(*args):
        entered.set()
        await resume.wait()
        return output

    client.run.side_effect = execute
    args = {"code": "print(3)", "dataset_ids": [dataset]}
    first = asyncio.create_task(tool.execute(args))
    try:
        await entered.wait()
        with pytest.raises(ResearchRejected, match="PYTHON_BUDGET_EXCEEDED"):
            await tool.execute(args)
    finally:
        resume.set()
        await first
    assert len(store._records) == 1


async def test_scoped_dataset_to_private_http_to_owned_artifact_round_trip():
    tool, dataset, _, store = setup()
    observed = []

    class Executor:
        async def run(self, code, datasets):
            observed.append((code, datasets))
            return SandboxResult("3", (SandboxArtifact("result.json", "application/json", b"3"),))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(Executor(), "x" * 43))
    ) as http:
        tool.client = SandboxClient(http, "http://127.0.0.1:8092", "x" * 43)
        result = await tool.execute({"code": "print(3)", "dataset_ids": [dataset]})
    assert observed == [("print(3)", [tool.datasets[dataset]])]
    assert result["dataset_ids"] == [dataset]
    assert next(iter(store._records.values())).owner == tool.guard.owner_hash
