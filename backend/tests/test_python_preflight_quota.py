from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI, Request
from test_research_public import plan
from test_research_python import setup
from test_research_python_integration import python_policy

from radar.config import Settings
from radar.postgres_repository import PostgresRepository
from radar.qa_limits import AskAdmission
from radar.research_endpoints import public_research_response
from radar.research_guard import ResearchRejected, canonical
from radar.sandbox_client import SandboxClient
from radar.sandbox_protocol import SandboxResult
from radar.schemas import AskRequest


async def test_unhealthy_sandbox_rejects_before_public_question_is_charged(tmp_path, monkeypatch):
    import radar.research_endpoints as endpoints

    app = FastAPI()
    policy = app.state.research_policy = python_policy(tmp_path)
    app.state.settings = Settings(
        llm_api_key="fixture",
        sandbox_controller_token="x" * 43,
        sandbox_image_id="sha256:" + "a" * 64,
    )
    app.state.ask_admission = AskAdmission()
    runtime = httpx.AsyncClient(
        base_url="http://pi",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"status": "ready", "python": True, "policy_digest": policy.digest}
            )
        ),
    )
    admission = AsyncMock()
    monkeypatch.setattr(endpoints, "begin_public_run", admission)
    monkeypatch.setattr(endpoints, "effective_model_settings", lambda value: value)
    monkeypatch.setattr(endpoints, "runtime_client", lambda *args: runtime)
    monkeypatch.setattr(
        SandboxClient, "ready", AsyncMock(side_effect=ResearchRejected("SANDBOX_UNAVAILABLE"))
    )

    @app.post("/ask")
    async def ask(request: Request):
        return await public_research_response(
            AskRequest(question="分析", client_request_id="test"),
            plan(),
            request,
            PostgresRepository(None, "fixture"),
            streaming=True,
        )

    async with httpx.AsyncClient(
        base_url="http://api", transport=httpx.ASGITransport(app=app)
    ) as client:
        response = await client.post("/ask")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_UNAVAILABLE"
    admission.assert_not_called()
    assert runtime.is_closed


async def test_control_characters_cannot_overflow_model_tool_result_after_json_encoding():
    tool, dataset, client, _ = setup()
    client.run.return_value = SandboxResult("\x01" * 20000, ())
    result = await tool.execute({"code": "print(1)", "dataset_ids": [dataset]})
    assert result["stdout_truncated"] is True
    assert len(canonical(result).encode()) < 32768
