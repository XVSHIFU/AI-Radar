"""One bounded, operator-invoked real-provider compatibility check.

Reads business events in a read-only snapshot. Paid calls are recorded as admin_test
in the existing usage table; this does not enable the public Agent or alter its quota.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import shutil
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
import uvicorn
from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import REPO_ROOT, Settings
from .deepseek_client import ProviderUsage
from .ingest.dns import configured_resolver
from .ingest.public_transport import PublicAsyncTransport
from .model_config import effective_model_settings
from .models import LlmCallRow
from .postgres_repository import PostgresRepository
from .research_gateway import ResearchSession
from .research_guard import ModelLease, ResearchGuard, ResearchRejected
from .research_http import ResearchSessions, research_router
from .research_policy import ANSWER_CONTRACT, ResearchPolicy
from .research_service import (
    finalize_answer,
    make_research_prompt,
    research_preflight,
    runtime_client,
    runtime_events,
)
from .research_stream import ResearchModelStream
from .research_tools import research_scope
from .schemas import AskRequest, Filters, QueryPlan


class VerificationLedger:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], run_id: UUID, settings: Settings
    ):
        self.sessions, self.run_id, self.settings = sessions, run_id, settings
        self.usage: list[dict[str, Any]] = []

    def key(self, sequence: int) -> str:
        return f"research-verify:{self.run_id}:{sequence}"

    async def claim(self, run_id: UUID, lease: ModelLease) -> None:
        if run_id != self.run_id or not 1 <= lease.sequence <= 3:
            raise ResearchRejected("RUN_NOT_FOUND")
        async with self.sessions() as session, session.begin():
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": int.from_bytes(run_id.bytes[:8], "big", signed=True)},
            )
            existing = await session.scalar(
                select(LlmCallRow.id).where(
                    LlmCallRow.logical_request_id == self.key(lease.sequence)
                )
            )
            if existing is not None:
                raise ResearchRejected("IDEMPOTENCY_REPLAY")
            session.add(
                LlmCallRow(
                    id=uuid4(),
                    ingest_run_id=None,
                    article_version_id=None,
                    logical_request_id=self.key(lease.sequence),
                    purpose="admin_test",
                    provider=self.settings.llm_provider,
                    model_id=self.settings.llm_model,
                    attempt=1,
                    status="pending",
                )
            )

    async def settle(
        self, run_id: UUID, lease: ModelLease, usage: ProviderUsage | None, status: str
    ) -> None:
        if run_id != self.run_id:
            raise ResearchRejected("RUN_NOT_FOUND")
        async with self.sessions() as session, session.begin():
            row = await session.scalar(
                select(LlmCallRow)
                .where(LlmCallRow.logical_request_id == self.key(lease.sequence))
                .with_for_update()
            )
            if row is None:
                raise ResearchRejected("RUN_NOT_FOUND")
            if row.status != "pending":
                return
            row.status, row.finished_at = status, datetime.now(UTC)
            if usage:
                row.prompt_tokens, row.completion_tokens, row.total_tokens = (
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                )
            self.usage.append(
                {
                    "sequence": lease.sequence,
                    "status": status,
                    "input": row.prompt_tokens,
                    "output": row.completion_tokens,
                    "input_reserved": lease.input_reserved,
                    "output_reserved": lease.output_reserved,
                }
            )


async def verify(config_root: Path, run_id: UUID) -> dict[str, Any]:
    settings = effective_model_settings(
        Settings(_env_file=config_root / ".env")  # type: ignore[call-arg]
    )
    if not settings.llm_api_key or not settings.sqlalchemy_url():
        raise ValueError("model/database configuration unavailable")
    policy = ResearchPolicy.load(REPO_ROOT / "agent/research")
    node = shutil.which("node")
    runtime_entry = REPO_ROOT / "agent/runtime/dist/src/server.js"
    if not node or not runtime_entry.is_file():
        raise ValueError("compiled pi runtime unavailable")
    engine = create_async_engine(settings.sqlalchemy_url())  # type: ignore[arg-type]
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ledger = VerificationLedger(sessions, run_id, settings)
    guard = ResearchGuard(run_id, "a" * 64, datetime.now(UTC) + timedelta(seconds=90))
    repository = PostgresRepository(
        sessions, settings.cursor_secret, timezone=settings.business_timezone
    )
    registry = ResearchSessions()
    app = FastAPI()
    app.include_router(research_router(registry))
    sock, runtime_sock = socket.socket(), socket.socket()
    sock.bind(("127.0.0.1", 0))
    runtime_sock.bind(("127.0.0.1", 0))
    runtime_port = runtime_sock.getsockname()[1]
    runtime_sock.close()
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    process = None
    started = monotonic()
    report: dict[str, Any] = {
        "run_id": str(run_id),
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "status": "failed",
        "usage": ledger.usage,
        "tools": [],
        "first_token_ms": None,
        "python": False,
        "public_agent_enabled": False,
    }
    provider = ResearchModelStream(
        settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_tokens=min(settings.llm_max_tokens, 512),
        transport=PublicAsyncTransport(resolver=configured_resolver(settings.fetch_dns_mode)),
    )
    try:
        async with asyncio.timeout(90):
            while not server.started:
                await asyncio.sleep(0.01)
            token = secrets.token_urlsafe(32)
            environment = {
                key: os.environ[key]
                for key in ("PATH", "SystemRoot", "TEMP", "TMP")
                if key in os.environ
            }
            environment.update(
                RADAR_RUNTIME_TOKEN=token,
                RADAR_BROKER_ORIGIN=f"http://127.0.0.1:{sock.getsockname()[1]}",
                RADAR_RUNTIME_HOST="127.0.0.1",
                PORT=str(runtime_port),
            )
            process = await asyncio.create_subprocess_exec(
                node,
                str(runtime_entry),
                cwd=REPO_ROOT,
                env=environment,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            async with runtime_client(f"http://127.0.0.1:{runtime_port}", token) as client:
                async with asyncio.timeout(10):
                    while True:
                        if process.returncode is not None:
                            raise ValueError("runtime failed to start")
                        try:
                            if (await client.get("/health")).status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        await asyncio.sleep(0.05)
                payload = AskRequest(
                    question=(
                        "请调用 aggregate_events 按分类统计当前范围的事件数量，"
                        "简短说明最多的类别和总数，引用统计依据。"
                    ),
                    client_request_id=str(run_id),
                )
                plan = QueryPlan(
                    intent="structured_summary",
                    filters=Filters(),
                    timezone=settings.business_timezone,
                    business_date=datetime.now(ZoneInfo(settings.business_timezone)).date(),
                    date_until_exclusive=None,
                    constraints_origin={},
                    free_text="",
                    requires_clarification=False,
                    clarification_candidates=[],
                    warnings=[],
                )
                await research_preflight(client, plan, settings, policy)
                async with research_scope(repository, guard, plan.filters, policy.skills) as tools:
                    prompt = make_research_prompt(payload, plan, tools)
                    session = ResearchSession(
                        guard=guard,
                        system=policy.system + "\n\n" + ANSWER_CONTRACT,
                        prompt=prompt,
                        provider=provider,
                        executor=tools,
                        ledger=ledger,
                    )
                    terminal = None
                    async with registry.register(session):
                        async for event in runtime_events(
                            client, prompt, provider.max_tokens, guard.capability
                        ):
                            if event["type"] == "text" and report["first_token_ms"] is None:
                                report["first_token_ms"] = round((monotonic() - started) * 1000)
                            if event["type"] == "tool" and event.get("phase") == "finished":
                                report["tools"].append(
                                    {
                                        "name": event.get("name"),
                                        "failed": event.get("failed", False),
                                    }
                                )
                            if event["type"] == "result":
                                terminal = event
                    if not terminal or terminal.get("status") != "completed":
                        report["error_code"] = (terminal or {}).get("code", "RESEARCH_INCOMPLETE")
                    else:
                        answer = finalize_answer(
                            terminal["answer"], tools.sources, payload.question
                        )
                        report.update(
                            answer=answer["answer"],
                            citation_count=len(answer["citations"]),
                            scope_total=await tools._count(),
                        )
                        if (
                            answer["citations"]
                            and ledger.usage
                            and all(
                                item["input"] is not None and item["output"] is not None
                                for item in ledger.usage
                            )
                            and any(
                                t["name"] == "aggregate_events" and not t["failed"]
                                for t in report["tools"]
                            )
                        ):
                            report["status"] = "passed"
    except Exception as exc:
        report["error_code"] = exc.code if isinstance(exc, ResearchRejected) else type(exc).__name__
    finally:
        guard.close()
        await provider.close()
        if process is not None and process.returncode is None:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5)
        server.should_exit = True
        await asyncio.wait_for(task, timeout=5)
        sock.close()
        await engine.dispose()
    report["duration_ms"] = round((monotonic() - started) * 1000)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", required=True, type=Path)
    parser.add_argument("--run-id", required=True, type=UUID)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    # A report must be new; a previous run is never silently overwritten/retried.
    fd = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump({"run_id": str(args.run_id), "status": "started"}, output)
        output.flush()
        os.fsync(output.fileno())
        try:
            report = asyncio.run(verify(args.config_root, args.run_id))
        except Exception as exc:
            report = {
                "run_id": str(args.run_id),
                "status": "failed",
                "error_code": type(exc).__name__,
            }
        output.seek(0)
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.truncate()
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
