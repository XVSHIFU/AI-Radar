"""Trusted research orchestration boundary; not mounted on the public API yet.

pi owns the loop, but cannot author the provider's system message, conversation,
tool schemas or results. A session starts with server-admitted input and only
appends actual provider replies and locally executed, scoped tool results.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .deepseek_client import ProviderUsage
from .model_stream import ModelStreamError
from .research_guard import ModelLease, RequestedTool, ResearchGuard, ResearchRejected, canonical
from .research_stream import ProviderTool, ResearchModelStream


class _Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Resolve(_Arguments):
    name: str = Field(min_length=1, max_length=100)


class _Search(_Arguments):
    query: str = Field(default="", max_length=200)
    cursor: str = Field(default="", max_length=200)
    sort: Literal["date", "importance"] = "date"


class _Evidence(_Arguments):
    event_ids: list[str] = Field(min_length=1, max_length=3)

    @field_validator("event_ids")
    @classmethod
    def valid_ids(cls, value: list[str]) -> list[str]:
        if any(len(item) != 36 for item in value):
            raise ValueError("invalid UUID length")
        if len({UUID(item) for item in value}) != len(value):
            raise ValueError("duplicate event")
        return value


class _Aggregate(_Arguments):
    dimension: Literal["date", "category", "date_category"]
    granularity: Literal["day", "month"] = "day"


class _Period(_Arguments):
    # Aliases preserve the model-facing contract while avoiding Python keywords.
    from_: str = Field(alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")
    to: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("from_", "to")
    @classmethod
    def valid_date(cls, value: str) -> str:
        date.fromisoformat(value)
        return value


class _Compare(_Arguments):
    first: _Period
    second: _Period


class _Chart(_Arguments):
    dataset_id: str
    kind: Literal["bar", "line", "heatmap"]

    @field_validator("dataset_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if len(value) != 36:
            raise ValueError("invalid UUID length")
        UUID(value)
        return value


class _Skill(_Arguments):
    name: Literal["explain-event", "compare-periods", "verify-evidence", "analyze-dataset"]


class _Python(_Arguments):
    code: str = Field(min_length=1, max_length=16384)
    dataset_ids: list[str] = Field(min_length=1, max_length=4)


SCHEMAS: dict[str, type[_Arguments]] = {
    "run_python": _Python,
    "resolve_entities": _Resolve,
    "search_events": _Search,
    "get_event_evidence": _Evidence,
    "aggregate_events": _Aggregate,
    "compare_periods": _Compare,
    "build_chart": _Chart,
    "load_research_skill": _Skill,
}
DESCRIPTIONS = {
    "run_python": (
        "Analyze only datasets returned in this run, in isolated Python. Once per run; "
        "numpy/pandas/matplotlib available. Write JSON/CSV/PNG to output_dir; "
        "cite the returned citation_index. No network or host access."
    ),
    "resolve_entities": "Resolve names in the authorized scope; report ambiguity.",
    "search_events": (
        "Search scoped articles and curated items; "
        "exact totals differ from returned pages."
    ),
    "get_event_evidence": "Read body evidence or labeled feed excerpts for up to three scoped IDs.",
    "aggregate_events": (
        "Count recorded items; use the returned unit and date basis, not unique events."
    ),
    "compare_periods": "Compare two date intervals within the same scope; report zero baselines.",
    "build_chart": "Chart a dataset returned in this run; never accept invented numbers.",
    "load_research_skill": "Read a registered skill. No paths, plugins or code execution.",
}


def provider_tools(*, python_enabled: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": DESCRIPTIONS[name],
                "parameters": schema.model_json_schema(by_alias=True),
            },
        }
        for name, schema in SCHEMAS.items()
        if name != "run_python" or python_enabled
    ]


class ScopedExecutor(Protocol):
    """Implementation is bound to an immutable server-owned scope and this run."""

    async def execute(self, name: str, arguments: dict[str, Any]) -> object: ...


class UsageLedger(Protocol):
    """Persistent accounting is mandatory, including reservations for unknown outcomes."""

    async def claim(self, run_id: UUID, lease: ModelLease) -> None: ...

    async def settle(
        self, run_id: UUID, lease: ModelLease, usage: ProviderUsage | None, status: str
    ) -> None: ...


_PUBLIC_ERRORS = frozenset(
    {
        "INVALID_ARGUMENT",
        "SCOPE_CHANGE_REQUIRED",
        "NOT_FOUND",
        "TOOL_UNAVAILABLE",
        "EXECUTION_TIMEOUT",
        "RESOURCE_LIMIT",
        "BUDGET_EXCEEDED",
    }
)


def _error(code: str) -> dict[str, object]:
    return {"error": {"code": code if code in _PUBLIC_ERRORS else "TOOL_UNAVAILABLE"}}


class ResearchSession:
    def __init__(
        self,
        *,
        guard: ResearchGuard,
        system: str,
        prompt: str,
        provider: ResearchModelStream,
        executor: ScopedExecutor,
        ledger: UsageLedger,
    ) -> None:
        self.guard = guard
        self.provider = provider
        self.executor = executor
        self.ledger = ledger
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        self._returned: dict[str, ProviderTool] = {}
        self.completed = False
        self._model_active = False

    def _tool_result(self, call_id: str, result: object) -> None:
        self._messages.append(
            {"role": "tool", "tool_call_id": call_id, "content": canonical(result)}
        )

    async def model(
        self,
        capability: str,
        sequence: int,
        max_output: int,
    ) -> AsyncGenerator[dict[str, object], None]:
        self.guard.check(capability)
        if self._model_active:
            raise ResearchRejected("RUN_BUSY")
        self._model_active = True
        stream = self._model(capability, sequence, max_output)
        try:
            async for item in stream:
                yield item
        finally:
            try:
                await stream.aclose()
            finally:
                self._model_active = False

    async def _model(
        self,
        capability: str,
        sequence: int,
        max_output: int,
    ) -> AsyncGenerator[dict[str, object], None]:
        """Never accepts system/context/messages/model/url from the runtime caller."""
        if self.completed:
            raise ResearchRejected("RUN_EXPIRED")
        request = self.provider.request_body(
            self._messages,
            provider_tools(python_enabled=self.guard.python_enabled) if sequence < 3 else [],
            min(max_output, self.provider.max_tokens),
        )
        lease = await self.guard.reserve_model(capability, sequence, request, max_output)
        request["max_tokens"] = min(lease.output_reserved, self.provider.max_tokens)
        usage: ProviderUsage | None = None
        requested: dict[str, RequestedTool] = {}
        status = "failed"
        claimed = False
        settled = False
        chunks: list[str] = []
        calls: tuple[ProviderTool, ...] = ()
        finish: str | None = None
        try:
            await self.ledger.claim(self.guard.run_id, lease)
            claimed = True
            timeout = max(0, (self.guard.deadline - datetime.now(UTC)).total_seconds())
            async with asyncio.timeout(timeout):
                stream = self.provider.stream_request(request)
                try:
                    async for delta in stream:
                        if delta.text:
                            chunks.append(delta.text)
                            yield {"type": "text", "text": delta.text}
                        if delta.finish:
                            usage, calls, finish = delta.usage, delta.tools, delta.finish
                finally:
                    await stream.aclose()
            if finish is None:
                raise ResearchRejected("TOOL_UNAVAILABLE")
            invalid: dict[str, str] = {}
            for call in calls:
                schema = SCHEMAS.get(call.name)
                if schema is None or (call.name == "run_python" and not self.guard.python_enabled):
                    invalid[call.id] = "TOOL_UNAVAILABLE"
                else:
                    try:
                        schema.model_validate(call.arguments)
                    except ValidationError:
                        invalid[call.id] = "INVALID_ARGUMENT"
                    else:
                        requested[call.id] = RequestedTool(call.name, call.arguments)
            # The guard independently authorizes only validated provider-issued calls.
            await self.guard.settle_model(
                capability,
                lease,
                input_tokens=usage.prompt_tokens if usage else None,
                output_tokens=usage.completion_tokens if usage else None,
                requested_tools=requested,
            )
            settled = True
            self.guard.check(capability)
            message: dict[str, Any] = {"role": "assistant", "content": "".join(chunks)}
            if calls:
                message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": canonical(call.arguments),
                        },
                    }
                    for call in calls
                ]
            self._messages.append(message)
            self._returned = {call.id: call for call in calls if call.id not in invalid}
            for call_id, code in invalid.items():
                # pi rejects unknown/invalid tools locally; consume these in our own
                # transcript so a subsequent model turn cannot deadlock on RUN_BUSY.
                self._tool_result(call_id, _error(code))
            for call in calls:
                yield {
                    "type": "tool",
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                }
            yield {
                "type": "usage",
                "input": usage.prompt_tokens if usage else None,
                "output": usage.completion_tokens if usage else None,
            }
            status = "completed" if finish != "length" else "truncated"
            self.completed = finish in {"stop", "length"}
            yield {"type": "finish", "reason": "toolUse" if finish == "tool_calls" else finish}
        except ModelStreamError as exc:
            usage = exc.usage
            raise
        except (asyncio.CancelledError, GeneratorExit):
            status = "cancelled"
            raise
        finally:
            try:
                if not settled:
                    await self.guard.settle_model(
                        capability,
                        lease,
                        input_tokens=usage.prompt_tokens if usage else None,
                        output_tokens=usage.completion_tokens if usage else None,
                    )
            finally:
                if status not in {"completed", "truncated"}:
                    self.guard.close()
                if claimed:
                    try:
                        await self.ledger.settle(self.guard.run_id, lease, usage, status)
                    except BaseException:
                        self.guard.close()
                        raise

    async def tool(
        self,
        capability: str,
        name: str,
        arguments: dict[str, Any],
        call_id: str,
    ) -> object:
        self.guard.check(capability)
        if self._model_active:
            raise ResearchRejected("RUN_BUSY")
        call = self._returned.get(call_id)
        if call is None or call.name != name or canonical(call.arguments) != canonical(arguments):
            raise ResearchRejected("INVALID_TOOL_CALL")
        # Refused budget calls become model-visible errors, but tampering above is a
        # protocol rejection and must not consume another valid call's authorization.
        active = False
        try:
            await self.guard.begin_tool(capability, call_id, name, arguments)
            active = True
            timeout = max(0, (self.guard.deadline - datetime.now(UTC)).total_seconds())
            async with asyncio.timeout(timeout):
                validated = SCHEMAS[name].model_validate(arguments).model_dump(by_alias=True)
                result = await self.executor.execute(name, validated)
                encoded = canonical(result)
                if len(encoded.encode("utf-8")) > 32768:
                    raise ResearchRejected("RESOURCE_LIMIT")
                result = json.loads(encoded)  # Own copy, with JSON-safe types only.
        except ResearchRejected as exc:
            if exc.code not in _PUBLIC_ERRORS:
                raise
            result = _error(exc.code)
        except TimeoutError:
            result = _error("EXECUTION_TIMEOUT")
        except asyncio.CancelledError:
            self.guard.close()
            raise
        except Exception:
            result = _error("TOOL_UNAVAILABLE")
        finally:
            if active:
                await self.guard.finish_tool(call_id)
        self.guard.check(capability)
        self._returned.pop(call_id, None)
        self._tool_result(call_id, result)
        return result
