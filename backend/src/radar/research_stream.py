"""Bounded tool streaming for the research gateway, separate from plain answers.

Inputs are constructed by the trusted gateway, never forwarded from pi context.
An assembled call is data, not authorization to execute it. The gateway must apply
its own schema, scope and per-run call authorization before invoking a tool.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from .deepseek_client import ProviderUsage
from .model_stream import ModelStreamError, OpenAiCompatibleStream

_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("non-finite JSON constant")


def strict_json(value: str) -> Any:
    return json.loads(value, object_pairs_hook=_object, parse_constant=_constant)


@dataclass(frozen=True)
class ProviderTool:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ResearchDelta:
    text: str = ""
    tools: tuple[ProviderTool, ...] = ()
    usage: ProviderUsage | None = None
    response_id: str | None = None
    finish: str | None = None


@dataclass
class _PartialTool:
    id: str = ""
    name: str = ""
    arguments: str = ""

    def append(self, delta: dict[str, Any]) -> None:
        if set(delta) - {"index", "id", "type", "function"}:
            raise ValueError("unexpected tool field")
        if delta.get("type", "function") != "function":
            raise ValueError("unsupported tool kind")
        call_id = delta.get("id")
        if call_id is not None:
            if not isinstance(call_id, str) or not _ID.fullmatch(call_id):
                raise ValueError("invalid tool id")
            if self.id and self.id != call_id:
                raise ValueError("changed tool id")
            self.id = call_id
        function = delta.get("function", {})
        if not isinstance(function, dict) or set(function) - {"name", "arguments"}:
            raise ValueError("invalid function")
        name = function.get("name")
        if name is not None:
            if not isinstance(name, str):
                raise ValueError("invalid tool name")
            self.name += name
        arguments = function.get("arguments")
        if arguments is not None:
            if not isinstance(arguments, str):
                raise ValueError("invalid argument fragment")
            self.arguments += arguments
        if len(self.name) > 64 or len(self.arguments.encode("utf-8")) > 16384:
            raise ValueError("tool size limit")

    def complete(self) -> ProviderTool:
        if not self.id or not _NAME.fullmatch(self.name):
            raise ValueError("incomplete tool")
        arguments = strict_json(self.arguments)
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        return ProviderTool(self.id, self.name, arguments)


@dataclass
class _State:
    usage: ProviderUsage | None = None
    response_id: str | None = None
    finish: str | None = None
    text_bytes: int = 0
    calls: dict[int, _PartialTool] = field(default_factory=dict)

    def chunk(self, body: object) -> str:
        if not isinstance(body, dict) or body.get("error"):
            raise ValueError("invalid provider envelope")
        chunk_id = body.get("id")
        if chunk_id is not None:
            if not isinstance(chunk_id, str) or len(chunk_id) > 200:
                raise ValueError("invalid response id")
            if self.response_id is not None and chunk_id != self.response_id:
                raise ValueError("changed response id")
            self.response_id = chunk_id
        usage = body.get("usage")
        if usage is not None:
            if not isinstance(usage, dict):
                raise ValueError("invalid usage")
            values = [usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")]
            if any(v is not None and (type(v) is not int or v < 0) for v in values):
                raise ValueError("invalid usage count")
            next_usage = ProviderUsage(*values)
            if self.usage is not None and self.usage != next_usage:
                raise ValueError("conflicting usage")
            self.usage = next_usage
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) > 1:
            raise ValueError("single completion required")
        if not choices:
            return ""
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("index", 0) != 0:
            raise ValueError("invalid completion")
        delta = choice.get("delta")
        delta = {} if delta is None else delta
        if not isinstance(delta, dict):
            raise ValueError("invalid delta")
        # Reasoning is intentionally neither exposed nor added to future messages.
        # It still counts against the total byte limit while reading the stream.
        if delta.get("function_call") or delta.get("refusal"):
            raise ValueError("unsupported completion")
        text = delta.get("content")
        if text is not None and not isinstance(text, str):
            raise ValueError("invalid content")
        text = text or ""
        calls = delta.get("tool_calls") or []
        if not isinstance(calls, list):
            raise ValueError("invalid calls")
        if self.finish is not None and (text or calls or delta.get("reasoning_content")):
            raise ValueError("content after finish")
        self.text_bytes += len(text.encode("utf-8"))
        if self.text_bytes > 48000:
            raise ValueError("answer size limit")
        for raw in calls:
            if not isinstance(raw, dict):
                raise ValueError("invalid call")
            index = raw.get("index")
            if type(index) is not int or not 0 <= index < 6:
                raise ValueError("tool count limit")
            self.calls.setdefault(index, _PartialTool()).append(raw)
        finish = choice.get("finish_reason")
        if finish is not None:
            if self.finish is not None or finish not in {"stop", "tool_calls", "length"}:
                raise ValueError("invalid finish")
            self.finish = finish
        return text

    def complete(self) -> tuple[ProviderTool, ...]:
        if self.finish not in {"stop", "tool_calls", "length"}:
            raise ValueError("missing finish")
        if self.finish == "length":
            # Truncated arguments are never executable.
            return ()
        if bool(self.calls) != (self.finish == "tool_calls"):
            raise ValueError("tool finish mismatch")
        if sorted(self.calls) != list(range(len(self.calls))):
            raise ValueError("non-contiguous tool indexes")
        tools = tuple(self.calls[k].complete() for k in sorted(self.calls))
        if len({call.id for call in tools}) != len(tools):
            raise ValueError("duplicate tool id")
        return tools


async def _sse_data(response: httpx.Response) -> AsyncIterator[str]:
    """Bound raw bytes before decoding; a missing newline cannot allocate without bound."""
    pending = bytearray()
    event_lines: list[str] = []
    total = 0
    async for block in response.aiter_bytes():
        total += len(block)
        if total > 262144:
            raise ValueError("stream size limit")
        pending.extend(block)
        while b"\n" in pending:
            raw, _, rest = pending.partition(b"\n")
            pending = bytearray(rest)
            line = raw.rstrip(b"\r").decode("utf-8", errors="strict")
            if line.startswith("data:"):
                event_lines.append(line[5:].removeprefix(" "))
                if sum(len(x.encode("utf-8")) for x in event_lines) > 65536:
                    raise ValueError("event size limit")
            elif not line and event_lines:
                yield "\n".join(event_lines)
                event_lines = []
        if len(pending) > 65536:
            raise ValueError("line size limit")
    if pending or event_lines:
        raise ValueError("incomplete SSE frame")


class ResearchModelStream(OpenAiCompatibleStream):
    """Shares configured HTTPS transport with plain answers, but never loosens that path."""

    def request_body(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], max_output: int
    ) -> dict[str, Any]:
        if type(max_output) is not int or not 1 <= max_output <= min(self.max_tokens, 2000):
            raise ValueError("invalid output limit")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": max_output,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if self.client.base_url.host in {"api.deepseek.com", "api.moonshot.cn"}:
            body["thinking"] = {"type": "disabled"}
        return body

    async def stream_request(
        self, request_body: dict[str, Any]
    ) -> AsyncGenerator[ResearchDelta, None]:
        state = _State()
        try:
            async with self.client.stream(
                "POST", "chat/completions", json=request_body
            ) as response:
                if response.is_redirect or response.is_error:
                    # Do not read provider error bodies, which can echo credentials or prompts.
                    raise ModelStreamError(
                        "provider rejected research request", code="provider_rejected"
                    )
                saw_done = False
                async for data in _sse_data(response):
                    if data == "[DONE]":
                        saw_done = True
                        break
                    text = state.chunk(strict_json(data))
                    if text:
                        yield ResearchDelta(text=text, response_id=state.response_id)
                if not saw_done:
                    raise ValueError("missing DONE")
                tools = state.complete()
            yield ResearchDelta(
                tools=tools,
                usage=state.usage,
                response_id=state.response_id,
                finish=state.finish,
            )
        except ModelStreamError:
            raise
        except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
            raise ModelStreamError(
                "invalid research provider stream",
                code="invalid_stream",
                unknown=True,
                usage=state.usage,
                response_id=state.response_id,
            ) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ModelStreamError(
                "research provider outcome is unknown",
                code="unknown_transport_failure",
                unknown=True,
                usage=state.usage,
                response_id=state.response_id,
            ) from exc
