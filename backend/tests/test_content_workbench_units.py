import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from radar.content_api import make_export, parse_import, validate_content
from radar.content_gateway import register
from radar.model_config import EffectiveModelConfig
from radar.models import ArticleVersionRow, ContentTaskRow


def test_export_bounds_long_frozen_article_and_checks_quote_scope() -> None:
    version = ArticleVersionRow(
        id=uuid4(),
        article_id=uuid4(),
        title="Frozen article",
        source_url="https://example.com/frozen",
        paragraphs={
            "p1": "Example AI released a model. " * 4000,
            "p2": "A second paragraph. " * 4000 + "UNEXPORTED_TAIL",
        },
        content_hash="a" * 64,
    )
    task = ContentTaskRow(
        id=uuid4(),
        article_version_id=version.id,
        content_hash=version.content_hash,
        prompt_version="content-v1",
        schema_version="extraction-v1",
        status="pending",
        mode="manual",
    )
    prompt, scopes = make_export([(task, version)])
    assert len(prompt.encode("utf-8")) <= 48_000
    assert scopes[task.id]["p1"] in version.paragraphs["p1"]
    assert scopes[task.id]["p1"] != version.paragraphs["p1"]
    content = {
        "relevant": True,
        "title_zh": "新模型发布",
        "summary_zh": "该机构发布模型。",
        "category": "model_release",
        "importance": 3,
        "entities": [{"canonical_name": "Example AI", "entity_type": "company", "role": "subject"}],
        "evidence": [{"paragraph_id": "p2", "quote_text": "UNEXPORTED_TAIL"}],
    }
    assert validate_content(content, scopes[task.id])
    assert parse_import("```json\n" + '{"results":[{"task_id":"x"}]}' + "\n```") == [
        {"task_id": "x"}
    ]


def test_content_gateway_capability_is_single_use_and_output_bound(client: TestClient) -> None:
    config = EffectiveModelConfig(
        api_key="not-used",
        enabled=True,
        max_tokens=30,
        credential_changed_at=None,
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
    )
    capability = asyncio.run(register(config, "frozen prompt", 30))
    response = client.post(
        "/internal/content/model",
        headers={"Authorization": f"Bearer {capability}"},
        json={"context": {}, "sequence": 1, "max_output": 31},
    )
    assert response.status_code == 422
    replay = client.post(
        "/internal/content/model",
        headers={"Authorization": f"Bearer {capability}"},
        json={"context": {}, "sequence": 1, "max_output": 30},
    )
    assert replay.status_code == 401
