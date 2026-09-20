"""Offline checks for relay retries and incremental fetching."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

SPEC = importlib.util.spec_from_file_location(
    "collect_sync", Path(__file__).resolve().parents[2] / "scripts" / "collect-sync.py"
)
relay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(relay)
RSS = b"<rss version='2.0'><channel><title>Feed</title><item><title>News</title><link>https://example.org/news</link><description>Summary</description></item></channel></rss>"


@pytest.mark.asyncio
async def test_body_failure_retries_but_acknowledged_body_is_not_fetched_again():
    config = {"feeds": [{"name": "Example", "url": "https://example.org/rss"}], "delay_seconds": 0}
    with patch.object(
        relay,
        "download",
        AsyncMock(
            side_effect=[("https://example.org/rss", RSS), httpx.ConnectError("unavailable")]
        ),
    ):
        first = await relay.collect(config, {})
    assert first["state"]["articles"] == {}
    assert len(first["batch"]["errors"]) == 1
    with patch.object(
        relay,
        "download",
        AsyncMock(
            side_effect=[
                ("https://example.org/rss", RSS),
                ("https://example.org/news", b"<p>Article</p>"),
            ]
        ),
    ):
        second = await relay.collect(config, first["state"])
    with patch.object(
        relay, "download", AsyncMock(return_value=("https://example.org/rss", RSS))
    ) as fetch:
        third = await relay.collect(config, second["state"])
    assert fetch.await_count == 1
    assert third["batch"]["feeds"][0]["bodies"] == {}


def test_failed_pending_delivery_does_not_advance_state_or_fetch_again(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}")
    folder = tmp_path / "collect-sync-state"
    folder.mkdir()
    packet = {"batch": {"id": "pending"}, "state": {"articles": {"new": "hash"}}}
    (folder / "pending.json").write_text(json.dumps(packet))
    (folder / "state.json").write_text('{"articles": {}}')
    with (
        patch("sys.argv", ["collect-sync", "--config", str(config)]),
        patch.object(relay, "send", side_effect=RuntimeError("SSH failed")),
        patch.object(relay, "collect") as collect,
    ):
        with pytest.raises(RuntimeError, match="SSH failed"):
            relay.main()
    assert (folder / "pending.json").exists()
    assert json.loads((folder / "state.json").read_text()) == {"articles": {}}
    collect.assert_not_called()


@pytest.mark.asyncio
async def test_proxy_fetch_rejects_private_literal_without_network_request():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="private address"):
            await relay.download(client, "http://127.0.0.1/private", "http://proxy")
