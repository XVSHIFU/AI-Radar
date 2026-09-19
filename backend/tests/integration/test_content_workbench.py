import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from radar.config import get_settings
from radar.main import app

pytestmark = pytest.mark.postgres


@pytest.fixture
def content_db(migration_database: object) -> object:
    migration_database.upgrade()
    return migration_database


async def _seed(database: object, paragraph: str = "Example AI released a new model.") -> str:
    source_id, article_id, version_id, run_id = [uuid4() for _ in range(4)]
    connection = await database.connect()
    try:
        await connection.execute(
            "INSERT INTO sources "
            "(id,name,feed_url,enabled,health,consecutive_failures,canonical_host,channel_type) "
            "VALUES ($1,$2,$3,true,'healthy',0,'example.com','rss')",
            source_id,
            f"content-{source_id}",
            "https://example.com/feed.xml",
        )
        await connection.execute(
            "INSERT INTO articles (id,source_id,canonical_url) VALUES ($1,$2,$3)",
            article_id,
            source_id,
            f"https://example.com/{article_id}",
        )
        await connection.execute(
            "INSERT INTO article_versions "
            "(id,article_id,title,source_url,paragraphs,content_hash) "
            "VALUES ($1,$2,'Frozen article',$3,$4::jsonb,$5)",
            version_id,
            article_id,
            f"https://example.com/{article_id}",
            json.dumps({"p-0001": paragraph}),
            "a" * 64,
        )
        await connection.execute(
            "INSERT INTO ingest_runs "
            "(id,idempotency_key,payload_hash,trigger_type,status) "
            "VALUES ($1,$2,$3,'manual','completed')",
            run_id,
            f"content-{run_id}",
            "b" * 64,
        )
        await connection.execute(
            "INSERT INTO article_candidates "
            "(id,run_id,source_id,article_version_id,canonical_url,original_url,title,status) "
            "VALUES ($1,$2,$3,$4,$5,$5,'Frozen article','needs_review')",
            uuid4(),
            run_id,
            source_id,
            version_id,
            f"https://example.com/{article_id}",
        )
    finally:
        await connection.close()
    return str(version_id)


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/admin/session", json={"token": "content-test-admin"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_manual_roundtrip_validation_idempotency_and_zero_model_calls(
    content_db: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    version_id = asyncio.run(_seed(content_db))
    monkeypatch.setenv("DATABASE_URL", content_db.rendered_url)
    monkeypatch.setenv("ADMIN_TOKEN", "content-test-admin")
    monkeypatch.setenv("MODEL_CONFIG_PATH", str(tmp_path / "model.json"))
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/admin/content/articles").status_code == 401
            headers = _auth(client)
            assert (
                client.post(
                    "/api/v1/admin/content/tasks",
                    json={"article_version_ids": [version_id]},
                ).status_code
                == 403
            )
            article_list = client.get("/api/v1/admin/content/articles").json()["items"]
            assert any(item["article_version_id"] == version_id for item in article_list)
            created = client.post(
                "/api/v1/admin/content/tasks",
                json={"article_version_ids": [version_id]},
                headers=headers,
            )
            assert created.status_code == 200, created.text
            task_id = created.json()["items"][0]["id"]
            exported = client.post(
                "/api/v1/admin/content/export",
                json={"task_ids": [task_id]},
                headers=headers,
            )
            assert exported.status_code == 200, exported.text
            assert "p-0001" in exported.json()["prompt"]
            assert len(exported.json()["prompt"].encode("utf-8")) <= 48_000
            content = {
                "task_id": task_id,
                "relevant": True,
                "title_zh": "新模型发布",
                "summary_zh": "该机构发布了新的人工智能模型。",
                "category": "model_release",
                "importance": 4,
                "entities": [
                    {"canonical_name": "Example AI", "entity_type": "company", "role": "subject"}
                ],
                "evidence": [{"paragraph_id": "p-0001", "quote_text": "invented quotation"}],
            }
            imported = client.post(
                "/api/v1/admin/content/import",
                json={"text": "```json\n" + json.dumps(content) + "\n```"},
                headers=headers,
            )
            assert imported.status_code == 200, imported.text
            first = imported.json()["items"][0]
            assert first["status"] == "invalid"
            assert "exact paragraph substring" in first["errors"][0]
            draft_id = first["draft_id"]
            content.pop("task_id")
            content["evidence"][0]["quote_text"] = "Example AI released a new model."
            updated = client.patch(
                f"/api/v1/admin/content/drafts/{draft_id}",
                json={"revision": 1, "content": content},
                headers=headers,
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["status"] == "needs_review"
            published = client.post(
                f"/api/v1/admin/content/drafts/{draft_id}/publish",
                json={"revision": 2},
                headers=headers,
            )
            assert published.status_code == 200, published.text
            assert published.json()["status"] == "published"
            again = client.post(
                f"/api/v1/admin/content/drafts/{draft_id}/publish",
                json={"revision": 2},
                headers=headers,
            )
            assert again.json()["event_id"] == published.json()["event_id"]
            assert client.get("/api/v1/admin/content/settings").json()["enabled"] is False
            assert (
                client.post(
                    "/api/v1/admin/content/batches",
                    json={"task_ids": [task_id]},
                    headers=headers,
                ).status_code
                == 409
            )

        async def verify() -> None:
            connection = await content_db.connect()
            try:
                assert await connection.fetchval("SELECT count(*) FROM evidence") == 1
                assert await connection.fetchval("SELECT count(*) FROM llm_calls") == 0
                assert await connection.fetchval("SELECT count(*) FROM events") == 1
            finally:
                await connection.close()

        asyncio.run(verify())
    finally:
        get_settings.cache_clear()


def test_content_claim_is_serial_and_daily_reservation_is_durable(
    content_db: object,
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from radar.config import Settings
    from radar.content_runner import _claim
    from radar.models import ContentBatchRow, ContentTaskRow

    first = asyncio.run(_seed(content_db))
    second = asyncio.run(_seed(content_db))
    batch_id, task_one, task_two = uuid4(), uuid4(), uuid4()

    async def exercise() -> None:
        engine = create_async_engine(content_db.rendered_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session, session.begin():
                settings = await session.get(
                    __import__("radar.models", fromlist=["ContentSettingsRow"]).ContentSettingsRow,
                    1,
                    with_for_update=True,
                )
                assert settings is not None
                settings.enabled = True
                settings.daily_article_limit = 2
                settings.daily_input_tokens = 100_000
                settings.daily_output_tokens = 10_000
                session.add(
                    ContentBatchRow(
                        id=batch_id,
                        status="queued",
                        profile={},
                        profile_version=settings.profile_version,
                        auto_publish=False,
                    )
                )
                for task_id, version_id in ((task_one, first), (task_two, second)):
                    session.add(
                        ContentTaskRow(
                            id=task_id,
                            article_version_id=__import__("uuid").UUID(version_id),
                            content_hash="a" * 64,
                            prompt_version="content-v1",
                            schema_version="extraction-v1",
                            status="queued_auto",
                            mode="auto",
                            batch_id=batch_id,
                        )
                    )
            configured = Settings(
                database_url=content_db.rendered_url,
                business_timezone="Asia/Shanghai",
            )
            claimed = await asyncio.gather(
                _claim(sessions, configured, batch_id),
                _claim(sessions, configured, batch_id),
            )
            assert sum(item is not None for item in claimed) == 1
            async with sessions() as session:
                from sqlalchemy import func, select

                from radar.models import ContentUsageRow

                assert await session.scalar(select(func.count()).select_from(ContentUsageRow)) == 1
                batch = await session.get(ContentBatchRow, batch_id)
                assert batch is not None and batch.status == "budget_paused"
            assert await _claim(sessions, configured, batch_id) is None
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_unknown_runtime_result_is_not_paid_retried(
    content_db: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from radar import content_runner
    from radar.config import Settings
    from radar.content_runner import process_batch
    from radar.model_config import EffectiveModelConfig
    from radar.models import ContentBatchRow, ContentTaskRow, ContentUsageRow

    version_id = asyncio.run(_seed(content_db))
    batch_id, task_id = uuid4(), uuid4()
    calls = 0

    async def unavailable(*args: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise RuntimeError("mock provider outcome unknown")

    monkeypatch.setattr(content_runner, "_run_runtime", unavailable)
    monkeypatch.setattr(
        content_runner.ModelConfigStore,
        "read",
        lambda self: EffectiveModelConfig(
            api_key="fixture-key",
            enabled=True,
            max_tokens=1600,
            credential_changed_at=None,
            provider="deepseek",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
        ),
    )

    async def exercise() -> None:
        engine = create_async_engine(content_db.rendered_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session, session.begin():
                from radar.models import ContentSettingsRow

                settings = await session.get(ContentSettingsRow, 1, with_for_update=True)
                assert settings is not None
                settings.enabled = True
                settings.daily_article_limit = 2
                settings.daily_input_tokens = 100_000
                settings.daily_output_tokens = 10_000
                session.add(
                    ContentBatchRow(
                        id=batch_id,
                        status="queued",
                        profile={},
                        profile_version=settings.profile_version,
                        auto_publish=False,
                    )
                )
                session.add(
                    ContentTaskRow(
                        id=task_id,
                        article_version_id=__import__("uuid").UUID(version_id),
                        content_hash="a" * 64,
                        prompt_version="content-v1",
                        schema_version="extraction-v1",
                        status="queued_auto",
                        mode="auto",
                        batch_id=batch_id,
                    )
                )
            configured = Settings(database_url=content_db.rendered_url)
            await process_batch(sessions, configured, batch_id)
            await process_batch(sessions, configured, batch_id)
            async with sessions() as session:
                task = await session.get(ContentTaskRow, task_id)
                usage = await session.scalar(
                    __import__("sqlalchemy")
                    .select(ContentUsageRow)
                    .where(ContentUsageRow.task_id == task_id)
                )
                assert task is not None and task.status == "unknown"
                assert usage is not None and usage.status == "unknown"
                assert usage.reserved_input_tokens > 0
            assert calls == 1
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("auto_publish", [False, True])
def test_successful_auto_result_respects_publish_switch(
    content_db: object, auto_publish: bool
) -> None:
    from datetime import date

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from radar.content_runner import _finish_success
    from radar.models import (
        ContentBatchRow,
        ContentDraftRow,
        ContentTaskRow,
        ContentUsageRow,
        EventRow,
    )

    version_id = asyncio.run(_seed(content_db))
    batch_id, task_id = uuid4(), uuid4()
    payload = {
        "task_id": str(task_id),
        "relevant": True,
        "title_zh": "新模型发布",
        "summary_zh": "该机构发布了新的人工智能模型。",
        "category": "model_release",
        "importance": 4,
        "entities": [{"canonical_name": "Example AI", "entity_type": "company", "role": "subject"}],
        "evidence": [{"paragraph_id": "p-0001", "quote_text": "Example AI released a new model."}],
    }

    async def exercise() -> None:
        engine = create_async_engine(content_db.rendered_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session, session.begin():
                session.add(
                    ContentBatchRow(
                        id=batch_id,
                        status="running",
                        profile={},
                        profile_version=1,
                        auto_publish=auto_publish,
                    )
                )
                session.add(
                    ContentTaskRow(
                        id=task_id,
                        article_version_id=__import__("uuid").UUID(version_id),
                        content_hash="a" * 64,
                        export_scope={"p-0001": "Example AI released a new model."},
                        prompt_version="content-v1",
                        schema_version="extraction-v1",
                        status="auto_processing",
                        mode="auto",
                        batch_id=batch_id,
                    )
                )
                session.add(
                    ContentUsageRow(
                        id=uuid4(),
                        task_id=task_id,
                        batch_id=batch_id,
                        usage_day=date.today(),
                        reserved_input_tokens=500,
                        reserved_output_tokens=100,
                        status="reserved",
                    )
                )
            result = {
                "status": "completed",
                "content": json.dumps(payload, ensure_ascii=False),
                "usage": {"input": 50, "output": 30},
            }
            assert await _finish_success(sessions, batch_id, task_id, result) is True
            async with sessions() as session:
                draft = await session.scalar(
                    select(ContentDraftRow).where(ContentDraftRow.task_id == task_id)
                )
                task = await session.get(ContentTaskRow, task_id)
                usage = await session.scalar(
                    select(ContentUsageRow).where(ContentUsageRow.task_id == task_id)
                )
                assert draft is not None and draft.validation_errors == []
                assert task is not None and task.mode == "auto"
                assert usage is not None and usage.status == "settled"
                assert draft.status == ("published" if auto_publish else "needs_review")
                assert await session.scalar(select(func.count()).select_from(EventRow)) == int(
                    auto_publish
                )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_superseded_article_never_reserves_paid_content_call(content_db: object) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from radar.config import Settings
    from radar.content_runner import _claim
    from radar.models import (
        ArticleVersionRow,
        ContentBatchRow,
        ContentSettingsRow,
        ContentTaskRow,
        ContentUsageRow,
    )

    version_id = asyncio.run(_seed(content_db))
    batch_id, task_id = uuid4(), uuid4()

    async def exercise() -> None:
        engine = create_async_engine(content_db.rendered_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session, session.begin():
                old = await session.get(ArticleVersionRow, __import__("uuid").UUID(version_id))
                assert old is not None
                session.add(
                    ArticleVersionRow(
                        id=uuid4(),
                        article_id=old.article_id,
                        title="New frozen version",
                        source_url=old.source_url,
                        paragraphs={"p-0001": "Updated article."},
                        content_hash="c" * 64,
                    )
                )
                settings = await session.get(ContentSettingsRow, 1, with_for_update=True)
                assert settings is not None
                settings.enabled = True
                settings.daily_article_limit = 1
                settings.daily_input_tokens = 100_000
                settings.daily_output_tokens = 10_000
                session.add(
                    ContentBatchRow(
                        id=batch_id,
                        status="queued",
                        profile={},
                        profile_version=settings.profile_version,
                        auto_publish=False,
                    )
                )
                session.add(
                    ContentTaskRow(
                        id=task_id,
                        article_version_id=old.id,
                        content_hash=old.content_hash,
                        prompt_version="content-v1",
                        schema_version="extraction-v1",
                        status="queued_auto",
                        mode="auto",
                        batch_id=batch_id,
                    )
                )
            result = await _claim(
                sessions, Settings(database_url=content_db.rendered_url), batch_id
            )
            assert result is None
            async with sessions() as session:
                task = await session.get(ContentTaskRow, task_id)
                assert task is not None and task.status == "validation_failed"
                assert await session.scalar(select(func.count()).select_from(ContentUsageRow)) == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())
