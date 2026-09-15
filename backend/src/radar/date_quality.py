from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from .models import EventDateAuditLogRow, EventRow, EvidenceRow

ISO_DATE = re.compile(r"(?<!\d)(20\d{2})-(0[1-9]|1[0-2])-([012]\d|3[01])(?!\d)")


@dataclass(frozen=True)
class DateCandidate:
    event_id: UUID
    current_date: date | None
    status: str
    candidates: tuple[tuple[date, UUID, str], ...]


class DateCorrectionRejected(ValueError):
    pass


class DateQualityService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def audit(self, *, limit: int = 1000) -> list[DateCandidate]:
        """Dry-run only: expose exact ISO dates in frozen quotes; never changes events."""
        async with self.sessions() as session:
            events = list(
                (
                    await session.scalars(
                        select(EventRow)
                        .where(EventRow.date_basis == "report_date_unverified")
                        .order_by(EventRow.id)
                        .limit(limit)
                    )
                ).all()
            )
            result = []
            for event in events:
                evidence = list(
                    (
                        await session.scalars(
                            select(EvidenceRow).where(EvidenceRow.event_id == event.id)
                        )
                    ).all()
                )
                found: list[tuple[date, UUID, str]] = []
                for item in evidence:
                    for match in ISO_DATE.finditer(item.quote_text):
                        try:
                            candidate = date.fromisoformat(match.group())
                        except ValueError:
                            continue
                        found.append((candidate, item.id, item.paragraph_id))
                distinct = {item[0] for item in found}
                if not distinct:
                    status = "no_explicit_date"
                elif len(distinct) == 1:
                    status = "candidate"
                else:
                    status = "conflict"
                result.append(DateCandidate(event.id, event.event_date, status, tuple(found)))
            return result

    async def apply(
        self, event_id: UUID, evidence_id: UUID, event_date: date, *, operator: str
    ) -> UUID:
        if not operator.strip():
            raise DateCorrectionRejected("operator is required")
        async with self.sessions() as session, session.begin():
            event = await session.get(EventRow, event_id, with_for_update=True)
            evidence = await session.scalar(
                select(EvidenceRow)
                .options(selectinload(EvidenceRow.article_version))
                .where(EvidenceRow.id == evidence_id, EvidenceRow.event_id == event_id)
            )
            if event is None or evidence is None:
                raise DateCorrectionRejected("event evidence does not exist")
            paragraph = evidence.article_version.paragraphs.get(evidence.paragraph_id)
            if (
                paragraph is None
                or evidence.quote_text not in paragraph
                or event_date.isoformat() not in evidence.quote_text
            ):
                raise DateCorrectionRejected("chosen date lacks exact frozen paragraph evidence")
            audit_id = uuid4()
            session.add(
                EventDateAuditLogRow(
                    id=audit_id,
                    event_id=event.id,
                    evidence_id=evidence.id,
                    before_date=event.event_date,
                    before_precision=event.date_precision,
                    before_basis=event.date_basis,
                    after_date=event_date,
                    after_precision="day",
                    after_basis="explicit_body",
                    operator=operator.strip(),
                )
            )
            event.event_date = event_date
            event.date_precision = "day"
            event.date_basis = "explicit_body"
            event.date_evidence_id = evidence.id
            event.content_version += 1
            return audit_id
