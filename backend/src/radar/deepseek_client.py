from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from .ingest.public_transport import PublicAsyncTransport, Resolver
from .model_config import normalize_base_url, normalize_model, normalize_provider


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class Completion:
    content: str
    response_id: str | None
    usage: ProviderUsage


class DeepSeekError(RuntimeError):
    def __init__(
        self, message: str, *, code: str, stop_batch: bool, completion: Completion | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stop_batch = stop_batch
        self.completion = completion


class DeepSeekClient:
    """OpenAI Chat Completions client; historical name retained for compatibility."""

    def __init__(
        self,
        api_key: str | None,
        *,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-flash",
        provider: str | None = None,
        max_tokens: int = 1600,
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        self._base_url = normalize_base_url(base_url)
        self._model = normalize_model(model)
        inferred = (
            "deepseek" if urlsplit(self._base_url).hostname == "api.deepseek.com" else "custom"
        )
        self._provider = normalize_provider(provider or inferred)
        if not 1 <= max_tokens <= 2000:
            raise ValueError("max_tokens must be between 1 and 2000")
        self._api_key = api_key
        self._max_tokens = max_tokens
        selected_transport = transport
        if selected_transport is None:
            selected_transport = (
                PublicAsyncTransport(resolver=resolver)
                if resolver is not None
                else PublicAsyncTransport()
            )
        self._client = httpx.AsyncClient(
            base_url=self._base_url.rstrip("/") + "/",
            timeout=timeout_seconds,
            transport=selected_transport,
            follow_redirects=False,
            trust_env=False,
        )

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    async def close(self) -> None:
        await self._client.aclose()

    async def complete_json(self, *, system: str, user: str) -> Completion:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        body: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        host = urlsplit(self._base_url).hostname
        if host in {"api.deepseek.com", "api.moonshot.cn"}:
            body["thinking"] = {"type": "disabled"}
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else None
        try:
            response = await self._client.post("chat/completions", headers=headers, json=body)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise DeepSeekError(
                "模型请求结果未知", code="unknown_transport_failure", stop_batch=False
            ) from exc
        body_text = response.text.lower()
        if response.status_code == 401:
            raise DeepSeekError("模型鉴权失败", code="authentication_failed", stop_batch=True)
        if response.status_code == 402 or "insufficient_balance" in body_text:
            raise DeepSeekError("模型余额不足", code="insufficient_balance", stop_batch=True)
        if response.is_error:
            raise DeepSeekError(
                f"模型服务拒绝请求（{response.status_code}）",
                code=f"provider_http_{response.status_code}",
                stop_batch=response.status_code in {403, 429},
            )
        completion: Completion | None = None
        try:
            payload: dict[str, Any] = response.json()
            usage = payload.get("usage") or {}
            completion = Completion(
                content="",
                response_id=payload.get("id"),
                usage=ProviderUsage(
                    prompt_tokens=_optional_int(usage.get("prompt_tokens")),
                    completion_tokens=_optional_int(usage.get("completion_tokens")),
                    total_tokens=_optional_int(usage.get("total_tokens")),
                ),
            )
            choice = payload["choices"][0]
            content = choice["message"]["content"]
            if isinstance(content, str):
                completion = Completion(content, completion.response_id, completion.usage)
            if choice.get("finish_reason") == "length":
                raise DeepSeekError(
                    "模型 JSON 响应被截断",
                    code="truncated_response",
                    stop_batch=False,
                    completion=completion,
                )
            if not isinstance(content, str) or not content.strip():
                raise DeepSeekError(
                    "模型返回空响应", code="empty_response", stop_batch=False, completion=completion
                )
            return completion
        except DeepSeekError:
            raise
        except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise DeepSeekError(
                "模型响应结构无效", code="invalid_response", stop_batch=False, completion=completion
            ) from exc


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
