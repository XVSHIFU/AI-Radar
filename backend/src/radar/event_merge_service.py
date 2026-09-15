from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import EventMergeLogRow, EventRow


class MergeRejected(ValueError):
    pass


class EventMergeService:
    """Reversible, operator-attributed canonicalization.

    Article and Evidence rows remain attached to their original event. Readers resolve a
    merged ID to its canonical event and include active member evidence, preserving every
    historical frozen relation.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def merge(
        self,
        source_id: UUID,
        target_id: UUID,
        *,
        reason: str,
        evidence: dict[str, object],
        operator: str,
    ) -> UUID:
        if source_id == target_id:
            raise MergeRejected("source and target must differ")
        if not reason.strip() or not operator.strip() or not evidence:
            raise MergeRejected("reason, evidence and operator are required")
        async with self.sessions() as session, session.begin():
            rows = list(
                (
                    await session.scalars(
                        select(EventRow)
                        .where(EventRow.id.in_((source_id, target_id)))
                        .order_by(EventRow.id)
                        .with_for_update()
                    )
                ).all()
            )
            by_id = {row.id: row for row in rows}
            source, target = by_id.get(source_id), by_id.get(target_id)
            if source is None or target is None:
                raise MergeRejected("source or target event does not exist")
            if source.status != "published" or source.merged_into_event_id is not None:
                raise MergeRejected("source event is not independently published")
            if target.status != "published" or target.merged_into_event_id is not None:
                raise MergeRejected("target event must be canonical and published")
            log_id = uuid4()
            session.add(
                EventMergeLogRow(
                    id=log_id,
                    source_event_id=source_id,
                    target_event_id=target_id,
                    reason=reason.strip(),
                    evidence=evidence,
                    operator=operator.strip(),
                    before_state={
                        "source_status": source.status,
                        "target_source_count": target.source_count,
                        "target_evidence_count": target.evidence_count,
                    },
                )
            )
            source.status = "merged"
            source.merged_into_event_id = target_id
            target.source_count += source.source_count
            target.evidence_count += source.evidence_count
            target.content_version += 1
            target.updated_at = datetime.now(UTC)
            return log_id

    async def unmerge(self, log_id: UUID, *, operator: str) -> None:
        if not operator.strip():
            raise MergeRejected("operator is required")
        async with self.sessions() as session, session.begin():
            log = await session.scalar(
                select(EventMergeLogRow)
                .where(EventMergeLogRow.id == log_id)
                .with_for_update()
            )
            if log is None or log.reverted_at is not None:
                raise MergeRejected("active merge log does not exist")
            source = await session.get(EventRow, log.source_event_id, with_for_update=True)
            target = await session.get(EventRow, log.target_event_id, with_for_update=True)
            if source is None or target is None or source.merged_into_event_id != target.id:
                raise MergeRejected("merge state no longer matches its audit log")
            source.status = str(log.before_state["source_status"])
            source.merged_into_event_id = None
            target.source_count = int(log.before_state["target_source_count"])
            target.evidence_count = int(log.before_state["target_evidence_count"])
            target.content_version += 1
            target.updated_at = datetime.now(UTC)
            log.reverted_at = datetime.now(UTC)
            log.reverted_by = operator.strip()
