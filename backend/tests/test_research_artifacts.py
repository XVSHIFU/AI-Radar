from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from radar.public_assistant import COOKIE
from radar.public_identity import PublicIdentity
from radar.research_artifacts import ArtifactStore, router
from radar.research_guard import ResearchRejected
from radar.sandbox_protocol import SandboxArtifact, SandboxResult

DATA = (str(uuid4()),)
RESULT = SandboxResult("", (SandboxArtifact("count.json", "application/json", b"3"),))


async def test_download_is_bound_to_cookie_owner_and_run_with_safe_headers():
    app = FastAPI()
    app.include_router(router)
    identity = app.state.public_identity = PublicIdentity("s" * 32)
    store = app.state.research_artifacts = ArtifactStore()
    cookie = identity.issue()
    run = uuid4()
    (item,) = store.publish(identity.subject(cookie), run, DATA, RESULT)
    url = f"/api/v1/assistant/runs/{run}/artifacts/{item.id}"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://radar"
    ) as client:
        assert (await client.get(url)).status_code == 404
        client.cookies.set(COOKIE, identity.issue())
        assert (await client.get(url)).status_code == 404
        client.cookies.set(COOKIE, cookie)
        assert (await client.get(url.replace(str(run), str(uuid4())))).status_code == 404
        response = await client.get(url)
    assert response.status_code == 200 and response.content == b"3"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == 'attachment; filename="count.json"'
    assert response.headers["content-type"] == "application/json"


def test_expiry_removes_bytes_and_run_tombstone():
    now = [0]
    store = ArtifactStore(clock=lambda: now[0])
    run = uuid4()
    (item,) = store.publish("a" * 64, run, DATA, RESULT)
    now[0] = 899
    assert store.get("a" * 64, run, item.id) is not None
    now[0] = 900
    assert store.get("a" * 64, run, item.id) is None
    assert not store._records and not store._runs


def test_publishing_again_does_not_overwrite_first_result_or_owner():
    store = ArtifactStore()
    run = uuid4()
    (item,) = store.publish("a" * 64, run, DATA, RESULT)
    with pytest.raises(ResearchRejected, match="JOB_REPLAY"):
        store.publish("b" * 64, run, DATA, RESULT)
    assert store.get("a" * 64, run, item.id) == item


def test_capacity_rejects_atomically_without_evicting_other_owners():
    store = ArtifactStore()
    large = SandboxResult(
        "", (SandboxArtifact("x.json", "application/json", b'"' + b"x" * 1048574 + b'"'),)
    )
    (first,) = store.publish("a" * 64, uuid4(), DATA, large)
    for _ in range(31):
        store.publish("b" * 64, uuid4(), DATA, large)
    with pytest.raises(ResearchRejected, match="RESOURCE_LIMIT"):
        store.publish("c" * 64, uuid4(), DATA, RESULT)
    assert len(store._records) == 32
    assert store.get(first.owner, first.run_id, first.id) == first
