from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class DeepSeekError(RuntimeError):
    def __init__(self, message: str, *, code: str, stop_batch: bool) -> None:
        super().__init__(message)
        self.code = code
        self.stop_batch = stop_batch


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


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-flash",
        max_tokens: int = 1600,
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if base_url.rstrip("/") != "https://api.deepseek.com":
            raise ValueError("DeepSeek base URL must be https://api.deepseek.com")
        if model != "deepseek-flash":
            raise ValueError("Only deepseek-flash is allowed")
        if not 1 <= max_tokens <= 2000:
            raise ValueError("max_tokens must be between 1 and 2000")
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url="https://api.deepseek.com",
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def complete_json(self, *, system: str, user: str) -> Completion:
        try:
            response = await self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "thinking": {"type": "disabled"},
                    "response_format": {"type": "json_object"},
                    "max_tokens": self._max_tokens,
                    "stream": False,
                },
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise DeepSeekError(
                "DeepSeek completion outcome is unknown",
                code="unknown_transport_failure",
                stop_batch=False,
            ) from exc
        body_text = response.text.lower()
        if response.status_code == 401:
            raise DeepSeekError(
                "DeepSeek authentication failed", code="authentication_failed", stop_batch=True
            )
        if response.status_code == 402 or "insufficient_balance" in body_text:
            raise DeepSeekError(
                "DeepSeek balance is insufficient", code="insufficient_balance", stop_batch=True
            )
        if response.is_error:
            raise DeepSeekError(
                f"DeepSeek rejected the completion ({response.status_code})",
                code=f"provider_http_{response.status_code}",
                stop_batch=response.status_code in {403, 429},
            )
        try:
            payload: dict[str, Any] = response.json()
            choice = payload["choices"][0]
            if choice.get("finish_reason") == "length":
                raise DeepSeekError(
                    "DeepSeek JSON was truncated", code="truncated_response", stop_batch=False
                )
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise DeepSeekError(
                    "DeepSeek returned empty JSON", code="empty_response", stop_batch=False
                )
            usage = payload.get("usage") or {}
            return Completion(
                content=content,
                response_id=payload.get("id"),
                usage=ProviderUsage(
                    prompt_tokens=_optional_int(usage.get("prompt_tokens")),
                    completion_tokens=_optional_int(usage.get("completion_tokens")),
                    total_tokens=_optional_int(usage.get("total_tokens")),
                ),
            )
        except DeepSeekError:
            raise
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise DeepSeekError(
                "DeepSeek response shape is invalid", code="invalid_response", stop_batch=False
            ) from exc


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
