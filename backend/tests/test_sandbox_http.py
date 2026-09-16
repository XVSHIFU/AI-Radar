import asyncio
import base64
import json
from uuid import uuid4

import httpx
import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_client import SandboxClient
from radar.sandbox_http import controller_app
from radar.sandbox_protocol import SandboxArtifact, SandboxResult

TOKEN = "a" * 43
DATA = [{"rows": [{"count": 3}]}]


class Executor:
    def __init__(self, block=False, failure=False):
        self.calls = []
        self.block = block
        self.failure = failure
        self.started = asyncio.Event()
        self.cleaned = asyncio.Event()

    async def run(self, code, datasets):
        self.calls.append((code, datasets))
        self.started.set()
        try:
            if self.block:
                await asyncio.Event().wait()
            if self.failure:
                raise ResearchRejected("EXECUTION_FAILED")
            return SandboxResult("3", (SandboxArtifact("answer.json", "application/json", b"3"),))
        finally:
            self.cleaned.set()


def body(job_id=None):
    return {"job_id": str(job_id or uuid4()), "code": "print(3)", "datasets": DATA}


async def test_round_trip_and_replay_do_not_execute_twice():
    executor = Executor()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(executor, TOKEN))
    ) as http:
        client = SandboxClient(http, "http://127.0.0.1:8092", TOKEN)
        job = uuid4()
        result = await client.run(job, "print(3)", DATA)
        assert result.stdout == "3"
        assert result.artifacts[0].content == b"3"
        with pytest.raises(ResearchRejected, match="SANDBOX_UNAVAILABLE"):
            await client.run(job, "print(4)", DATA)
    assert executor.calls == [("print(3)", DATA)]


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("authorization", "Bearer wrong")],
        [("authorization", "Bearer " + TOKEN), ("authorization", "Bearer " + TOKEN)],
    ],
)
async def test_auth_before_parsing(headers):
    executor = Executor()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(executor, TOKEN)),
        base_url="http://controller",
    ) as http:
        response = await http.post("/v1/execute", content=b"not-json", headers=headers)
    assert response.status_code == 401
    assert not executor.calls


@pytest.mark.parametrize("extra", [{"image": "python"}, {"shell": True}, {"owner": "x"}])
async def test_cannot_override_execution_authority(extra):
    executor = Executor()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(executor, TOKEN)),
        base_url="http://controller",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as http:
        response = await http.post("/v1/execute", json={**body(), **extra})
    assert response.status_code == 400
    assert not executor.calls


async def test_failed_execution_is_not_retryable_with_same_id():
    executor = Executor(failure=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(executor, TOKEN)),
        base_url="http://controller",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as http:
        payload = body()
        first = await http.post("/v1/execute", json=payload)
        second = await http.post("/v1/execute", json=payload)
    assert (first.status_code, second.status_code) == (503, 409)
    assert len(executor.calls) == 1


async def test_concurrency_rejects_third_and_cancel_cleans():
    executor = Executor(block=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=controller_app(executor, TOKEN)),
        base_url="http://controller",
        headers={"Authorization": "Bearer " + TOKEN},
    ) as http:
        tasks = [asyncio.create_task(http.post("/v1/execute", json=body())) for _ in range(2)]
        try:
            async with asyncio.timeout(2):
                while len(executor.calls) < 2:
                    await asyncio.sleep(0)
            third = await http.post("/v1/execute", json=body())
            assert third.status_code == 429
        finally:
            for task in tasks:
                task.cancel()
            async with asyncio.timeout(2):
                await asyncio.gather(*tasks, return_exceptions=True)
        assert executor.cleaned.is_set()
        executor.block = False
        assert (await http.post("/v1/execute", json=body())).status_code == 200


async def test_real_asgi_disconnect_cancels_execution_and_keeps_tombstone():
    executor = Executor(block=True)
    app = controller_app(executor, TOKEN)
    payload = body()
    messages = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": json.dumps(payload).encode()}
        await executor.started.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/execute",
            "query_string": b"",
            "headers": [(b"authorization", ("Bearer " + TOKEN).encode())],
            "scheme": "http",
            "server": ("controller", 80),
            "client": ("api", 1),
            "root_path": "",
            "http_version": "1.1",
        },
        receive,
        send,
    )
    assert executor.cleaned.is_set()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://controller"
    ) as http:
        response = await http.post(
            "/v1/execute", json=payload, headers={"Authorization": "Bearer " + TOKEN}
        )
    assert response.status_code == 409
    assert len(executor.calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"Location": "http://public.invalid"}),
        httpx.Response(200, content=b'{"status":"completed"}'),
        httpx.Response(
            200,
            json={
                "status": "completed",
                "stdout": "",
                "artifacts": [{"name": "../secret.json", "data": base64.b64encode(b"3").decode()}],
            },
        ),
    ],
)
async def test_client_rejects_redirect_or_untrusted_output_without_retry(response):
    calls = []

    def handler(request):
        calls.append(request)
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SandboxClient(http, "http://127.0.0.1:8092", TOKEN)
        with pytest.raises(ResearchRejected):
            await client.run(uuid4(), "print(3)", DATA)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url", ["http://169.254.169.254", "https://example.com", "http://sandbox-controller:8092/path"]
)
def test_client_destination_is_operator_allowlisted(url):
    with pytest.raises(ValueError):
        SandboxClient(None, url, TOKEN)
