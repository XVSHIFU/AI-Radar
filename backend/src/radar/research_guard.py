"""Per-run capability and budget guards. PostgreSQL public quota remains authoritative.

These guards live outside pi and the model. A lost process loses capabilities, never
restores them from user input, and leaves the persistent maximum reservation charged.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from .public_quota import HEX_KEY, REQUEST_KEY

ALLOWED_TOOLS = frozenset(
    {
        "resolve_entities",
        "search_events",
        "get_event_evidence",
        "aggregate_events",
        "compare_periods",
        "build_chart",
        "load_research_skill",
    }
)


class ResearchRejected(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def canonical(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


@dataclass(frozen=True)
class ModelLease:
    sequence: int
    input_reserved: int
    output_reserved: int


@dataclass(frozen=True)
class RequestedTool:
    name: str
    arguments: dict[str, Any]


class ResearchGuard:
    def __init__(
        self, run_id: UUID, owner_hash: str, deadline: datetime, *, python_enabled: bool = False
    ) -> None:
        if not HEX_KEY.fullmatch(owner_hash) or deadline.tzinfo is None:
            raise ValueError("server-owned run identity required")
        self.run_id = run_id
        self.owner_hash = owner_hash
        self.deadline = deadline
        self.capability = secrets.token_urlsafe(32)
        self._lock = asyncio.Lock()
        self._closed = False
        self._lease: ModelLease | None = None
        self.model_calls = 0
        self.input_charge = 0
        self.output_charge = 0
        self.python_enabled = python_enabled
        self.python_calls = 0
        self.business_calls = 0
        self.skill_calls = 0
        self._pending: dict[str, RequestedTool] = {}
        self._tool_active: str | None = None
        self._finished: set[str] = set()

    def check(self, capability: str) -> None:
        if not capability.isascii() or not hmac.compare_digest(capability, self.capability):
            raise ResearchRejected("RUN_NOT_FOUND")
        if self._closed or datetime.now(UTC) >= self.deadline:
            raise ResearchRejected("RUN_EXPIRED")

    def close(self) -> None:
        self._closed = True
        self._pending.clear()

    async def reserve_model(
        self, capability: str, sequence: int, request_body: dict[str, object], max_output: int
    ) -> ModelLease:
        async with self._lock:
            self.check(capability)
            if self._lease or self._tool_active or self._pending:
                raise ResearchRejected("RUN_BUSY")
            if type(sequence) is not int or sequence != self.model_calls + 1:
                raise ResearchRejected("IDEMPOTENCY_REPLAY")
            if type(max_output) is not int or not 1 <= max_output <= 2000:
                raise ResearchRejected("INVALID_ARGUMENT")
            # Estimate the complete provider request, including instructions, tools and history.
            size = len(canonical(request_body).encode("utf-8")) + 1024
            remaining_output = min(max_output, 4800 - self.output_charge)
            if self.model_calls >= 3 or self.input_charge + size > 24000 or remaining_output <= 0:
                raise ResearchRejected("BUDGET_EXCEEDED")
            self.model_calls += 1
            self._lease = ModelLease(sequence, size, remaining_output)
            self.input_charge += size
            self.output_charge += remaining_output
            return self._lease

    async def settle_model(
        self,
        capability: str,
        lease: ModelLease,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        requested_tools: dict[str, RequestedTool] | None = None,
    ) -> None:
        # Settlement is allowed after cancellation/expiry; it cannot grant new tool permissions.
        async with self._lock:
            if not capability.isascii() or not hmac.compare_digest(capability, self.capability):
                raise ResearchRejected("RUN_NOT_FOUND")
            if lease != self._lease:
                raise ResearchRejected("IDEMPOTENCY_REPLAY")
            for value in (input_tokens, output_tokens):
                if value is not None and (type(value) is not int or value < 0):
                    raise ResearchRejected("INVALID_USAGE")
            if requested_tools:
                if len(requested_tools) > 6:
                    raise ResearchRejected("RESOURCE_LIMIT")
                for call_id, call in requested_tools.items():
                    if not REQUEST_KEY.fullmatch(call_id) or call_id in self._finished:
                        raise ResearchRejected("INVALID_TOOL_CALL")
                    if len(canonical(call.arguments).encode("utf-8")) > 16384:
                        raise ResearchRejected("RESOURCE_LIMIT")
            self.input_charge += (
                input_tokens if input_tokens is not None else lease.input_reserved
            ) - lease.input_reserved
            self.output_charge += (
                output_tokens if output_tokens is not None else lease.output_reserved
            ) - lease.output_reserved
            self._lease = None
            if requested_tools:
                if not self._closed and datetime.now(UTC) < self.deadline:
                    # Deep-copy provider data: mutable arguments cannot rewrite the authorization.
                    self._pending = {
                        key: RequestedTool(call.name, json.loads(canonical(call.arguments)))
                        for key, call in requested_tools.items()
                    }

    async def begin_tool(self, capability: str, call_id: str, name: str, arguments: object) -> None:
        async with self._lock:
            self.check(capability)
            if self._lease or self._tool_active:
                raise ResearchRejected("RUN_BUSY")
            if call_id in self._finished:
                raise ResearchRejected("IDEMPOTENCY_REPLAY")
            call = self._pending.get(call_id)
            if (
                call is None
                or call.name != name
                or canonical(call.arguments) != canonical(arguments)
            ):
                raise ResearchRejected("INVALID_TOOL_CALL")
            # Consume the provider call even when refused. It cannot be retried under another name.
            del self._pending[call_id]
            self._finished.add(call_id)
            if name not in ALLOWED_TOOLS and not (name == "run_python" and self.python_enabled):
                raise ResearchRejected("TOOL_UNAVAILABLE")
            is_skill = name == "load_research_skill"
            if self.input_charge > 24000 or self.output_charge > 4800:
                raise ResearchRejected("BUDGET_EXCEEDED")
            if self.model_calls >= 3 or (
                self.skill_calls >= 2 if is_skill else self.business_calls >= 4
            ):
                raise ResearchRejected("BUDGET_EXCEEDED")
            if name == "run_python":
                if self.python_calls >= 1:
                    raise ResearchRejected("BUDGET_EXCEEDED")
                self.python_calls += 1
            if is_skill:
                self.skill_calls += 1
            else:
                self.business_calls += 1
            self._tool_active = call_id

    async def finish_tool(self, call_id: str) -> None:
        async with self._lock:
            if self._tool_active != call_id:
                raise ResearchRejected("INVALID_TOOL_CALL")
            self._tool_active = None


class RunCapabilities:
    """A bounded process-local directory; API restart revokes every old capability."""

    def __init__(self) -> None:
        self._runs: dict[str, ResearchGuard] = {}

    def add(self, guard: ResearchGuard) -> None:
        now = datetime.now(UTC)
        self._runs = {
            key: run for key, run in self._runs.items() if not run._closed and run.deadline > now
        }
        if len(self._runs) >= 2:
            raise ResearchRejected("RUN_BUSY")
        key = hashlib.sha256(guard.capability.encode()).hexdigest()
        self._runs[key] = guard

    def get(self, capability: str) -> ResearchGuard:
        if len(capability) > 128 or not capability.isascii():
            raise ResearchRejected("RUN_NOT_FOUND")
        guard = self._runs.get(hashlib.sha256(capability.encode()).hexdigest())
        if guard is None:
            raise ResearchRejected("RUN_NOT_FOUND")
        guard.check(capability)
        return guard

    def remove(self, guard: ResearchGuard) -> None:
        guard.close()
        self._runs.pop(hashlib.sha256(guard.capability.encode()).hexdigest(), None)
