from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from .deepseek_client import ProviderUsage


@dataclass(frozen=True)
class StreamDelta:
    text: str = ""
    usage: ProviderUsage | None = None
    response_id: str | None = None
    done: bool = False


class ModelStreamError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        unknown: bool = False,
        usage: ProviderUsage | None = None,
        response_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.unknown = unknown
        self.usage = usage
        self.response_id = response_id


class OpenAiCompatibleStream:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str,
        max_tokens: int,
        transport: httpx.AsyncBaseTransport,
    ) -> None:
        parts = urlsplit(base_url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise ValueError(
                "model base URL must be an absolute HTTPS URL without credentials or query"
            )
        self.model = model
        self.max_tokens = max_tokens
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            transport=transport,
            timeout=60,
            follow_redirects=False,
            trust_env=False,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def stream(self, *, system: str, user: str) -> AsyncIterator[StreamDelta]:
        usage = None
        response_id = None
        saw_done = False
        finish = None
        request_body: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": self.max_tokens,
        }
        if self.client.base_url.host in {"api.deepseek.com", "api.moonshot.cn"}:
            request_body["thinking"] = {"type": "disabled"}
        try:
            async with self.client.stream(
                "POST", "chat/completions", json=request_body
            ) as response:
                if response.is_redirect:
                    raise ModelStreamError("provider redirect rejected", code="provider_redirect")
                if response.status_code == 401:
                    raise ModelStreamError(
                        "provider authentication failed", code="authentication_failed"
                    )
                if response.status_code == 402:
                    raise ModelStreamError(
                        "provider balance is insufficient", code="insufficient_balance"
                    )
                if response.is_error:
                    raise ModelStreamError(
                        "provider rejected stream", code=f"provider_http_{response.status_code}"
                    )
                async for line in response.aiter_lines():
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line[5:].lstrip()
                    if data == "[DONE]":
                        saw_done = True
                        break
                    try:
                        body = json.loads(data)
                        if not isinstance(body, dict):
                            raise TypeError("provider chunk must be an object")
                    except (ValueError, TypeError) as exc:
                        raise ModelStreamError(
                            "invalid provider SSE JSON", code="invalid_stream"
                        ) from exc
                    chunk_id = body.get("id")
                    if isinstance(chunk_id, str):
                        response_id = chunk_id
                    raw_usage = body.get("usage")
                    if isinstance(raw_usage, dict):
                        usage = ProviderUsage(
                            _int(raw_usage.get("prompt_tokens")),
                            _int(raw_usage.get("completion_tokens")),
                            _int(raw_usage.get("total_tokens")),
                        )
                        yield StreamDelta(usage=usage, response_id=response_id)
                    choices = body.get("choices", [])
                    if not isinstance(choices, list):
                        raise ModelStreamError(
                            "provider choices are invalid",
                            code="invalid_stream",
                            usage=usage,
                            response_id=response_id,
                        )
                    for choice in choices:
                        if not isinstance(choice, dict):
                            raise ModelStreamError(
                                "provider choice is invalid",
                                code="invalid_stream",
                                usage=usage,
                                response_id=response_id,
                            )
                        raw_delta = choice.get("delta")
                        delta = {} if raw_delta is None else raw_delta
                        if not isinstance(delta, dict):
                            raise ModelStreamError(
                                "provider delta is invalid",
                                code="invalid_stream",
                                usage=usage,
                                response_id=response_id,
                            )
                        if finish is not None and delta:
                            raise ModelStreamError(
                                "provider sent data after finish",
                                code="data_after_finish",
                                usage=usage,
                                response_id=response_id,
                            )
                        if delta.get("tool_calls") or delta.get("function_call"):
                            raise ModelStreamError(
                                "tool output is forbidden",
                                code="tool_output",
                                usage=usage,
                                response_id=response_id,
                            )
                        text = delta.get("content")
                        if isinstance(text, str) and text:
                            yield StreamDelta(text=text, response_id=response_id)
                        if choice.get("finish_reason") is not None:
                            finish = choice["finish_reason"]
        except ModelStreamError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ModelStreamError(
                "provider stream outcome is unknown",
                code="unknown_transport_failure",
                unknown=True,
                usage=usage,
                response_id=response_id,
            ) from exc
        if not saw_done:
            raise ModelStreamError(
                "provider stream ended without DONE",
                code="incomplete_stream",
                unknown=True,
                usage=usage,
                response_id=response_id,
            )
        if finish != "stop":
            raise ModelStreamError(
                "provider stream did not finish normally",
                code="truncated_response" if finish == "length" else "invalid_finish",
                usage=usage,
                response_id=response_id,
            )
        yield StreamDelta(usage=usage, response_id=response_id, done=True)


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
