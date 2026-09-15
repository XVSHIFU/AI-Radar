from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import ArticleRow, EventArticleRow, EventMergeLogRow, EventRow, EvidenceRow


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
            source_has_members = await session.scalar(
                select(EventRow.id)
                .where(EventRow.merged_into_event_id == source_id)
                .limit(1)
            )
            if source_has_members is not None:
                raise MergeRejected("a canonical event with merged members cannot become a member")
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
                        "source_source_count": source.source_count,
                        "source_evidence_count": source.evidence_count,
                        "target_source_count": target.source_count,
                        "target_evidence_count": target.evidence_count,
                    },
                )
            )
            source.status = "merged"
            source.merged_into_event_id = target_id
            await session.flush()
            target.source_count, target.evidence_count = await self._canonical_counts(
                session, target_id
            )
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
            await session.flush()
            target.source_count, target.evidence_count = await self._canonical_counts(
                session, target.id
            )
            target.content_version += 1
            target.updated_at = datetime.now(UTC)
            log.reverted_at = datetime.now(UTC)
            log.reverted_by = operator.strip()

    async def _canonical_counts(
        self, session: AsyncSession, canonical_id: UUID
    ) -> tuple[int, int]:
        member_ids = select(EventRow.id).where(
            or_(
                EventRow.id == canonical_id,
                EventRow.merged_into_event_id == canonical_id,
            )
        )
        source_count = int(
            (
                await session.scalar(
                    select(func.count(func.distinct(ArticleRow.source_id)))
                    .select_from(EventArticleRow)
                    .join(ArticleRow, ArticleRow.id == EventArticleRow.article_id)
                    .where(EventArticleRow.event_id.in_(member_ids))
                )
            )
            or 0
        )
        evidence_count = int(
            (
                await session.scalar(
                    select(func.count(EvidenceRow.id)).where(
                        EvidenceRow.event_id.in_(member_ids)
                    )
                )
            )
            or 0
        )
        return source_count, evidence_count
