import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from radar.deepseek_client import (
    Completion,
    DeepSeekClient,
    DeepSeekError,
    ProviderUsage,
)
from radar.extraction_schemas import ExtractionResult
from radar.extraction_service import ExtractionService


def _response(content: str = "{}", *, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "provider-response",
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        },
    )


@pytest.mark.asyncio
async def test_deepseek_request_is_fixed_nonthinking_json() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return _response('{"relevant": false}')

    client = DeepSeekClient("test-key", transport=httpx.MockTransport(handler))
    try:
        completion = await client.complete_json(system="JSON only", user="article")
    finally:
        await client.close()

    assert seen["url"] == "https://api.deepseek.com/chat/completions"
    assert seen["authorization"] == "Bearer test-key"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-flash"
    assert body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"}
    assert body["stream"] is False
    assert body["max_tokens"] <= 2000
    assert completion.usage.total_tokens == 18


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (_response("", finish_reason="stop"), "empty_response"),
        (_response("{}", finish_reason="length"), "truncated_response"),
        (httpx.Response(401, json={"error": "unauthorized"}), "authentication_failed"),
        (httpx.Response(402, json={"error": "insufficient_balance"}), "insufficient_balance"),
        (httpx.Response(400, json={"error": "insufficient_balance"}), "insufficient_balance"),
    ],
)
async def test_deepseek_failures_are_classified(response: httpx.Response, code: str) -> None:
    client = DeepSeekClient("test-key", transport=httpx.MockTransport(lambda _: response))
    try:
        with pytest.raises(DeepSeekError) as captured:
            await client.complete_json(system="JSON only", user="article")
    finally:
        await client.close()
    assert captured.value.code == code
    assert captured.value.stop_batch is (code in {"authentication_failed", "insufficient_balance"})
    if code in {"empty_response", "truncated_response"}:
        assert captured.value.completion is not None
        assert captured.value.completion.usage.total_tokens == 18
    else:
        assert captured.value.completion is None


@pytest.mark.asyncio
async def test_timeout_is_unknown_and_never_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("unknown", request=request)

    client = DeepSeekClient("test-key", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(DeepSeekError) as captured:
            await client.complete_json(system="JSON only", user="article")
    finally:
        await client.close()
    assert captured.value.code == "unknown_transport_failure"
    assert calls == 1


def test_evidence_must_be_exact_frozen_paragraph_substring() -> None:
    valid = ExtractionResult.model_validate(
        {
            "relevant": True,
            "title_zh": "发布新模型",
            "summary_zh": "公司发布了新模型。",
            "category": "model_release",
            "importance": 4,
            "entities": [
                {
                    "canonical_name": "Example AI",
                    "entity_type": "company",
                    "role": "subject",
                }
            ],
            "evidence": [{"paragraph_id": "p-0001", "quote_text": "released a model"}],
        }
    )
    valid.validate_publishable({"p-0001": "The company released a model today."})

    invalid = valid.model_copy(
        update={"evidence": [valid.evidence[0].model_copy(update={"quote_text": "invented"})]}
    )
    with pytest.raises(ValueError, match="exact paragraph substring"):
        invalid.validate_publishable({"p-0001": "The company released a model today."})


@pytest.mark.parametrize("content", ["", "not-json", '{"relevant":'])
def test_bad_json_is_rejected(content: str) -> None:
    with pytest.raises(ValueError):
        ExtractionResult.model_validate_json(content)


def test_publishable_event_requires_chinese_and_nonblank_structural_fields() -> None:
    payload = {
        "relevant": True,
        "title_zh": "English only",
        "summary_zh": "公司发布模型。",
        "category": "model_release",
        "importance": 4,
        "entities": [{"canonical_name": "Example AI", "entity_type": "company", "role": "subject"}],
        "evidence": [{"paragraph_id": "p-0001", "quote_text": "released"}],
    }
    extraction = ExtractionResult.model_validate(payload)
    with pytest.raises(ValueError, match="Chinese"):
        extraction.validate_publishable({"p-0001": "released"})

    payload["title_zh"] = "发布模型"
    payload["entities"][0]["canonical_name"] = " "
    extraction = ExtractionResult.model_validate(payload)
    with pytest.raises(ValueError, match="must not be blank"):
        extraction.validate_publishable({"p-0001": "released"})

    payload["entities"][0]["canonical_name"] = "Example AI"
    payload["evidence"][0]["quote_text"] = " "
    extraction = ExtractionResult.model_validate(payload)
    with pytest.raises(ValueError, match="exact paragraph substring"):
        extraction.validate_publishable({"p-0001": "released text"})


@pytest.mark.asyncio
async def test_invalid_shape_retains_usage_when_response_is_parseable() -> None:
    response = httpx.Response(
        200,
        json={
            "id": "provider-response",
            "choices": [],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        },
    )
    client = DeepSeekClient("test-key", transport=httpx.MockTransport(lambda _: response))
    try:
        with pytest.raises(DeepSeekError) as captured:
            await client.complete_json(system="JSON only", user="article")
    finally:
        await client.close()
    assert captured.value.code == "invalid_response"
    assert captured.value.completion is not None
    assert captured.value.completion.usage.total_tokens == 18


@pytest.mark.asyncio
async def test_version_failure_cannot_reuse_previous_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_version = uuid4()
    second_version = uuid4()
    first_call = uuid4()
    second_call = uuid4()

    class OneCompletionClient:
        async def complete_json(self, *, system: str, user: str) -> Completion:
            return Completion(
                '{"relevant": false}',
                "first-response",
                ProviderUsage(101, 7, 108),
            )

    service = ExtractionService(None, OneCompletionClient())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_provider_blocked", AsyncMock(return_value=False))
    monkeypatch.setattr(
        service,
        "_eligible_versions",
        AsyncMock(
            return_value=[
                (first_version, date(2026, 9, 1)),
                (second_version, date(2026, 9, 2)),
            ]
        ),
    )
    monkeypatch.setattr(service, "_claim", AsyncMock(side_effect=[first_call, second_call]))
    monkeypatch.setattr(
        service,
        "_version",
        AsyncMock(
            side_effect=[
                SimpleNamespace(title="first", paragraphs={"p-0001": "first"}),
                ValueError("version disappeared"),
            ]
        ),
    )
    finish = AsyncMock()
    fail = AsyncMock()
    monkeypatch.setattr(service, "_finish_without_event", finish)
    monkeypatch.setattr(service, "_fail", fail)

    result = await service.run(date(2026, 9, 1), date(2026, 9, 2), 2)

    assert (result.filtered, result.failed) == (1, 1)
    assert finish.await_args.args[3].usage.total_tokens == 108
    fail.assert_awaited_once_with(second_call, second_version, "invalid_extraction")
