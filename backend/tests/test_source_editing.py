from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.requests import Request

from radar import admin_api
from radar.models import SourceRow


class Session:
    def __init__(self, row):
        self.row = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def begin(self):
        return self

    async def get(self, *args, **kwargs):
        return self.row


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    [
        "AWS Machine Learning",
        "Google Research",
        "Hugging Face",
        "NVIDIA Technical Blog",
        "Microsoft Research",
    ],
)
async def test_all_sources_allow_name_and_url_edits(name, monkeypatch):
    row = SourceRow(
        id=uuid4(),
        name=name,
        feed_url="https://example.com/old",
        enabled=True,
        channel_type="rss",
        etag="old",
        last_modified="old",
        health="healthy",
    )
    state = SimpleNamespace(
        sessions=lambda: Session(row), settings=SimpleNamespace(fetch_dns_mode="system")
    )
    request = Request({"type": "http", "app": SimpleNamespace(state=state)})
    checked = []

    async def resolve(url, resolver):
        checked.append(url)

    monkeypatch.setattr(admin_api, "resolve_public", resolve)
    response = await admin_api.patch_source(
        row.id, admin_api.SourcePatch(name="Edited", feed_url="https://example.com/new"), request
    )
    assert response["editable"] is True
    assert response["id"] == str(row.id)
    assert response["name"] == "Edited"
    assert response["feed_url"] == "https://example.com/new"
    assert checked == ["https://example.com/new"]
    assert row.etag is None
    assert row.last_modified is None
    assert row.health == "unknown"
