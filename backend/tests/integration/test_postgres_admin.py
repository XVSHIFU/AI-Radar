import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

import radar.admin_api as admin_api
from radar.config import get_settings
from radar.main import app

pytestmark = pytest.mark.postgres


@contextmanager
def _client(database: Any, monkeypatch: pytest.MonkeyPatch, config_path: Path):
    monkeypatch.setenv("RADAR_DATA_MODE", "postgres")
    monkeypatch.setenv("DATABASE_URL", database.rendered_url)
    monkeypatch.setenv("ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setenv("MODEL_CONFIG_PATH", str(config_path))
    get_settings.cache_clear()
    with TestClient(app) as client:

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/models":
                return httpx.Response(200, json={"data": [{"id": "deepseek-flash"}]})
            if request.url.path in {"/feed", "/news/"}:
                return httpx.Response(
                    200,
                    content=b"<rss><channel><item><title>One</title>"
                    b"<link>https://example.com/one</link></item></channel></rss>",
                )
            body = __import__("json").loads(request.content)
            assert body["model"] == "deepseek-flash"
            assert body["max_tokens"] <= 32
            assert body["thinking"] == {"type": "disabled"}
            return httpx.Response(
                200,
                json={
                    "id": "admin-test-response",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": '{"ok":true}'},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 8,
                        "completion_tokens": 3,
                        "total_tokens": 11,
                    },
                },
            )

        transport = httpx.MockTransport(handler)
        app.state.admin_model_transport = transport
        app.state.admin_http_transport = transport
        yield client
    get_settings.cache_clear()


async def _seed(database: Any) -> tuple[str, str]:
    builtin_id, custom_id = uuid4(), uuid4()
    connection = await database.connect()
    try:
        await connection.execute(
            "INSERT INTO sources "
            "(id,name,feed_url,enabled,health,consecutive_failures,canonical_host,channel_type) "
            "VALUES ($1,'OpenAI','https://openai.com/news/',true,'unknown',0,'openai.com','archive'),"
            "($2,$3,'https://example.com/feed',true,'unknown',0,'example.com','rss')",
            builtin_id,
            custom_id,
            f"custom-{custom_id}",
        )
        for total in (17, None):
            call_id = uuid4()
            await connection.execute(
                "INSERT INTO llm_calls "
                "(id,logical_request_id,purpose,provider,model_id,attempt,status,"
                "prompt_tokens,completion_tokens,total_tokens) "
                "VALUES ($1,$2,'event_extraction','deepseek','deepseek-flash',1,"
                "'completed',$3,$4,$5)",
                call_id,
                f"admin-ledger-{call_id}",
                10 if total else None,
                7 if total else None,
                total,
            )
    finally:
        await connection.close()
    return str(builtin_id), str(custom_id)


def test_admin_sources_and_usage_live_postgres(
    postgres_database: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    builtin_id, custom_id = asyncio.run(_seed(postgres_database))

    async def public_resolver(_host: str) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(admin_api, "configured_resolver", lambda _mode: public_resolver)
    with _client(postgres_database, monkeypatch, tmp_path / "model.json") as client:
        assert client.get("/api/v1/admin/sources").status_code == 401
        headers = {"Authorization": "Bearer admin-test-token"}
        response = client.get("/api/v1/admin/sources", headers=headers)
        assert response.status_code == 200
        selected = {item["id"]: item for item in response.json()["items"]}
        assert selected[builtin_id]["editable"] is False
        assert selected[custom_id]["editable"] is True
        immutable = client.patch(
            f"/api/v1/admin/sources/{builtin_id}", json={"name": "renamed"}, headers=headers
        )
        assert immutable.status_code == 422
        assert immutable.json()["code"] == "SOURCE_IMMUTABLE"
        assert (
            client.patch(
                f"/api/v1/admin/sources/{custom_id}", json={"name": None}, headers=headers
            ).status_code
            == 422
        )
        changed = client.patch(
            f"/api/v1/admin/sources/{custom_id}",
            json={"name": f"renamed-{custom_id}"},
            headers=headers,
        )
        assert changed.status_code == 200
        probe = client.post(f"/api/v1/admin/sources/{custom_id}/probe", headers=headers)
        assert probe.status_code == 200
        assert probe.json()["items_found"] == 1
        assert (
            client.post(f"/api/v1/admin/sources/{custom_id}/probe", headers=headers).status_code
            == 429
        )
        archive_probe = client.post(f"/api/v1/admin/sources/{builtin_id}/probe", headers=headers)
        assert archive_probe.status_code == 200
        assert archive_probe.json()["message"] == "归档页面可访问"
        presets = client.get("/api/v1/admin/model/presets", headers=headers)
        assert presets.status_code == 200
        assert {item["id"] for item in presets.json()["items"]} == {
            "deepseek",
            "openai",
            "qwen",
            "moonshot",
        }
        configured = client.put(
            "/api/v1/admin/model",
            json={"api_key": "test-only-key", "enabled": True, "max_tokens": 64},
            headers=headers,
        )
        assert configured.status_code == 200
        assert "api_key" not in configured.json()
        rejected = client.put(
            "/api/v1/admin/model",
            json={
                "enabled": True,
                "max_tokens": 64,
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4.1-mini",
            },
            headers=headers,
        )
        assert rejected.status_code == 422
        current = client.get("/api/v1/admin/model", headers=headers).json()
        assert current["provider"] == "deepseek"
        connectivity = client.post(
            "/api/v1/admin/model/test", json={"kind": "connectivity"}, headers=headers
        )
        assert connectivity.json()["ok"] is True
        assert connectivity.json()["request_messages"]
        completion = client.post(
            "/api/v1/admin/model/test", json={"kind": "completion"}, headers=headers
        )
        assert completion.json()["usage"]["total_tokens"] == 11
        assert completion.json()["response_text"] == '{"ok":true}'
        assert completion.json()["request_messages"][0]["role"] == "system"
        usage = client.get("/api/v1/admin/model/usage", headers=headers)
        assert usage.status_code == 200
        row = next(
            item
            for item in usage.json()["items"]
            if item["purpose"] == "event_extraction" and item["status"] == "completed"
        )
        assert row["calls"] >= 2
        assert row["usage_recorded"] >= 1
        assert row["total_tokens"] is not None

        async def failing_resolver(_host: str) -> list[str]:
            raise OSError("dns unavailable")

        monkeypatch.setattr(admin_api, "configured_resolver", lambda _mode: failing_resolver)
        disabled = client.put(
            "/api/v1/admin/model",
            json={"enabled": False, "max_tokens": 64},
            headers=headers,
        )
        assert disabled.status_code == 200
        invalid = client.put(
            "/api/v1/admin/model",
            json={
                "enabled": False,
                "max_tokens": 64,
                "base_url": "http://127.0.0.1/v1",
                "api_key": "replacement",
            },
            headers=headers,
        )
        assert invalid.status_code == 422
        assert client.get("/api/v1/ingest/runs").status_code == 401
