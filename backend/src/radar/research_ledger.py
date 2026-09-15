"""Persistent per-model reservations under an already admitted public question."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from .deepseek_client import ProviderUsage
from .models import Base, LlmCallRow
from .public_quota import HEX_KEY, PublicAskRow
from .research_guard import ModelLease, ResearchRejected


class ResearchCallRow(Base):
    __tablename__ = "research_model_calls"

    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public_ask_requests.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_call_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("llm_calls.id"))
    input_reserved: Mapped[int] = mapped_column(Integer)
    output_reserved: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("model_call_id", name="uq_research_model_call"),
        CheckConstraint("sequence BETWEEN 1 AND 3", name="ck_research_sequence"),
        CheckConstraint("input_reserved BETWEEN 1 AND 24000", name="ck_research_input"),
        CheckConstraint("output_reserved BETWEEN 1 AND 2000", name="ck_research_output"),
    )


async def research_usage(
    session: AsyncSession,
    run_id: UUID,
) -> tuple[int, int, int]:
    """Unknown or in-flight usage consumes its persisted reservation, never zero."""
    rows = (
        await session.execute(
            select(ResearchCallRow, LlmCallRow)
            .join(LlmCallRow, ResearchCallRow.model_call_id == LlmCallRow.id)
            .where(ResearchCallRow.run_id == run_id)
        )
    ).all()
    return (
        len(rows),
        sum(
            call.prompt_tokens if call.prompt_tokens is not None else entry.input_reserved
            for entry, call in rows
        ),
        sum(
            call.completion_tokens if call.completion_tokens is not None else entry.output_reserved
            for entry, call in rows
        ),
    )


class PostgresResearchLedger:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        owner_hash: str,
        *,
        provider: str,
        model: str,
    ) -> None:
        if not HEX_KEY.fullmatch(owner_hash):
            raise ValueError("server-owned identity required")
        self.sessions = sessions
        self.owner_hash = owner_hash
        self.provider = provider
        self.model = model

    async def claim(self, run_id: UUID, lease: ModelLease) -> None:
        if (
            type(lease.sequence) is not int
            or not 1 <= lease.sequence <= 3
            or type(lease.input_reserved) is not int
            or not 1 <= lease.input_reserved <= 24000
            or type(lease.output_reserved) is not int
            or not 1 <= lease.output_reserved <= 2000
        ):
            raise ResearchRejected("BUDGET_EXCEEDED")
        async with self.sessions() as session, session.begin():
            parent = await session.scalar(
                select(PublicAskRow)
                .where(
                    PublicAskRow.id == run_id,
                    PublicAskRow.owner_hash == self.owner_hash,
                )
                .with_for_update()
            )
            now = await session.scalar(select(func.clock_timestamp()))
            assert isinstance(now, datetime)
            if parent is None:
                raise ResearchRejected("RUN_NOT_FOUND")
            if parent.status != "reserved" or not parent.charged or parent.active_until <= now:
                raise ResearchRejected("RUN_EXPIRED")
            rows = (
                await session.execute(
                    select(ResearchCallRow, LlmCallRow)
                    .join(LlmCallRow, ResearchCallRow.model_call_id == LlmCallRow.id)
                    .where(ResearchCallRow.run_id == run_id)
                    .order_by(ResearchCallRow.sequence)
                )
            ).all()
            if lease.sequence != len(rows) + 1:
                raise ResearchRejected("IDEMPOTENCY_REPLAY")
            if any(call.status != "completed" for _, call in rows):
                raise ResearchRejected("RUN_BUSY")
            input_charge = sum(
                call.prompt_tokens if call.prompt_tokens is not None else entry.input_reserved
                for entry, call in rows
            )
            output_charge = sum(
                call.completion_tokens
                if call.completion_tokens is not None
                else entry.output_reserved
                for entry, call in rows
            )
            if input_charge + lease.input_reserved > min(
                parent.input_charge, 24000
            ) or output_charge + lease.output_reserved > min(parent.output_charge, 4800):
                raise ResearchRejected("BUDGET_EXCEEDED")
            call_id = uuid4()
            session.add(
                LlmCallRow(
                    id=call_id,
                    logical_request_id=f"research:{run_id.hex}:{lease.sequence}",
                    purpose="answer_generation",
                    provider=self.provider,
                    model_id=self.model,
                    attempt=1,
                    currency="USD",
                    cost_status="unknown",
                    status="pending",
                )
            )
            await session.flush()
            session.add(
                ResearchCallRow(
                    run_id=run_id,
                    sequence=lease.sequence,
                    model_call_id=call_id,
                    input_reserved=lease.input_reserved,
                    output_reserved=lease.output_reserved,
                )
            )

    async def settle(
        self,
        run_id: UUID,
        lease: ModelLease,
        usage: ProviderUsage | None,
        status: str,
    ) -> None:
        if status not in {"completed", "cancelled", "failed", "truncated"}:
            raise ValueError("invalid terminal status")
        if usage is not None:
            for value in (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens):
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError("invalid usage")
        async with self.sessions() as session, session.begin():
            # Same lock order as claim; cancellation may already have finalized the parent.
            parent = await session.scalar(
                select(PublicAskRow)
                .where(
                    PublicAskRow.id == run_id,
                    PublicAskRow.owner_hash == self.owner_hash,
                )
                .with_for_update()
            )
            if parent is None:
                raise ResearchRejected("RUN_NOT_FOUND")
            row = (
                await session.execute(
                    select(ResearchCallRow, LlmCallRow)
                    .join(LlmCallRow, ResearchCallRow.model_call_id == LlmCallRow.id)
                    .where(
                        ResearchCallRow.run_id == run_id, ResearchCallRow.sequence == lease.sequence
                    )
                )
            ).one_or_none()
            if row is None:
                raise ResearchRejected("INVALID_TOOL_CALL")
            entry, call = row
            if (entry.input_reserved, entry.output_reserved) != (
                lease.input_reserved,
                lease.output_reserved,
            ):
                raise ResearchRejected("IDEMPOTENCY_REPLAY")
            if call.status != "pending":
                return  # Immutable terminal usage, including an unknown result.
            call.status = status
            call.finished_at = await session.scalar(select(func.clock_timestamp()))
            if usage is not None:
                call.prompt_tokens = usage.prompt_tokens
                call.completion_tokens = usage.completion_tokens
                call.total_tokens = usage.total_tokens


async def finish_public_question(
    sessions: async_sessionmaker[AsyncSession],
    run_id: UUID,
    owner_hash: str,
    legacy_request_id: str,
    *,
    completed: bool,
) -> None:
    """Lock the parent before reading calls, excluding races with a new paid claim."""
    async with sessions() as session, session.begin():
        parent = await session.scalar(
            select(PublicAskRow)
            .where(
                PublicAskRow.id == run_id,
                PublicAskRow.owner_hash == owner_hash,
            )
            .with_for_update()
        )
        if parent is None:
            raise ResearchRejected("RUN_NOT_FOUND")
        if parent.status != "reserved":
            return
        count, input_charge, output_charge = await research_usage(session, run_id)
        legacy = await session.scalar(
            select(LlmCallRow).where(
                LlmCallRow.purpose == "answer_generation",
                LlmCallRow.logical_request_id == f"answer:{legacy_request_id}",
            )
        )
        started = completed or count > 0 or legacy is not None
        parent.status = "finished" if started else "rejected"
        now = await session.scalar(select(func.clock_timestamp()))
        assert isinstance(now, datetime)
        parent.active_until = now
        parent.settled_at = parent.active_until
        parent.charged = started
        if legacy is None or legacy.prompt_tokens is not None:
            parent.input_charge = input_charge + ((legacy.prompt_tokens or 0) if legacy else 0)
        if legacy is None or legacy.completion_tokens is not None:
            parent.output_charge = output_charge + (
                (legacy.completion_tokens or 0) if legacy else 0
            )
