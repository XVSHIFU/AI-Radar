from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from .cursor import decode_cursor, encode_cursor
from .db_schema import SCHEMA_REVISION
from .models import (
    EntityAliasRow,
    EntityRow,
    EventEntityRow,
    EventRow,
    EvidenceRow,
    SourceRow,
)
from .normalize import normalize_text
from .queryplanner import EntityResolution, ResolvedEntity, resolve_confirmed_entities
from .repository import EvidenceInvalid, InsightsSnapshot, Page, RepositoryUnavailable
from .schemas import Article, Category, Event, Evidence, Filters


class PostgresRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        cursor_secret: str,
        timezone: str = "Asia/Shanghai",
    ):
        self.sessions = sessions
        self.cursor_secret = cursor_secret
        self.timezone = ZoneInfo(timezone)

    def _filters(self, filters: Filters) -> list[Any]:
        clauses: list[Any] = [EventRow.status == "published"]
        if filters.event_ids:
            clauses.append(EventRow.id.in_(filters.event_ids))
        if filters.category:
            clauses.append(EventRow.category == filters.category.value)
        if filters.date_from:
            clauses.extend(
                (EventRow.date_precision == "day", EventRow.event_date >= filters.date_from)
            )
        if filters.date_to:
            clauses.extend(
                (EventRow.date_precision == "day", EventRow.event_date <= filters.date_to)
            )
        if filters.min_importance:
            clauses.append(EventRow.importance >= filters.min_importance)
        if filters.q:
            query = normalize_text(filters.q)
            alias_ids = select(EntityAliasRow.entity_id).where(
                EntityAliasRow.normalized_alias == query
            )
            alias_exists = exists().where(EntityAliasRow.normalized_alias == query)
            subject_match = exists().where(
                and_(
                    EventEntityRow.event_id == EventRow.id,
                    EventEntityRow.entity_id.in_(alias_ids),
                    EventEntityRow.role.in_(("subject", "product")),
                )
            )
            text_match = or_(
                EventRow.title_zh.ilike(f"%{query}%"),
                EventRow.summary_zh.ilike(f"%{query}%"),
            )
            clauses.append(case((alias_exists, subject_match), else_=text_match))
        entity_ids = set(filters.entity_ids)
        if entity_ids:
            matches = (
                select(func.count(func.distinct(EventEntityRow.entity_id)))
                .where(
                    and_(
                        EventEntityRow.event_id == EventRow.id,
                        EventEntityRow.entity_id.in_(entity_ids),
                        EventEntityRow.role.in_(("subject", "product")),
                    )
                )
                .scalar_subquery()
            )
            clauses.append(matches >= (len(entity_ids) if filters.entity_match == "all" else 1))
        return clauses

    async def resolve_entities(self, text: str) -> EntityResolution:
        normalized = normalize_text(text)
        try:
            async with self.sessions() as session:
                rows = (
                    (
                        await session.execute(
                            select(EntityRow).options(selectinload(EntityRow.aliases))
                        )
                    )
                    .scalars()
                    .all()
                )
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL entity resolution failed") from exc
        aliases: dict[str, list[ResolvedEntity]] = {}
        for row in rows:
            entity = ResolvedEntity(row.canonical_name, UUID(str(row.id)))
            aliases.setdefault(normalize_text(row.canonical_name), []).append(entity)
            for entity_alias in row.aliases:
                aliases.setdefault(entity_alias.normalized_alias, []).append(entity)
        return resolve_confirmed_entities(normalized, aliases)

    async def list_events(self, filters: Filters, limit: int, cursor: str | None) -> Page:
        clauses = self._filters(filters)
        if cursor:
            last_date, last_id = decode_cursor(cursor, filters, self.cursor_secret)
            if last_date is None:
                clauses.append(and_(EventRow.event_date.is_(None), EventRow.id < last_id))
            else:
                clauses.append(
                    or_(
                        EventRow.event_date < last_date,
                        and_(EventRow.event_date == last_date, EventRow.id < last_id),
                        EventRow.event_date.is_(None),
                    )
                )
        try:
            async with self.sessions() as session, session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                total = int(
                    (
                        await session.scalar(
                            select(func.count())
                            .select_from(EventRow)
                            .where(*self._filters(filters))
                        )
                    )
                    or 0
                )
                statement = (
                    select(EventRow)
                    .options(selectinload(EventRow.entities).selectinload(EventEntityRow.entity))
                    .where(*clauses)
                    .order_by(EventRow.event_date.desc().nulls_last(), EventRow.id.desc())
                    .limit(limit + 1)
                )
                rows = list((await session.scalars(statement)).all())
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            encode_cursor(rows[-1].event_date, rows[-1].id, filters, self.cursor_secret)
            if more
            else None
        )
        return Page(
            [self._event(row) for row in rows],
            total,
            next_cursor,
            datetime.now(UTC),
            "postgres-live-no-cross-page-snapshot",
        )

    def _event(self, row: EventRow) -> Event:
        return Event(
            id=row.id,
            title_zh=row.title_zh,
            summary_zh=row.summary_zh,
            category=row.category,
            importance=row.importance,
            event_date=row.event_date,
            date_precision=row.date_precision,
            source_count=row.source_count,
            evidence_count=row.evidence_count,
            entities=[relation.entity.canonical_name for relation in row.entities],
            content_version=row.content_version,
        )

    async def event(self, event_id: UUID) -> Event | None:
        try:
            async with self.sessions() as session:
                requested = await session.get(EventRow, event_id)
                canonical_id = (
                    requested.merged_into_event_id
                    if requested is not None and requested.merged_into_event_id is not None
                    else event_id
                )
                row = await session.scalar(
                    select(EventRow)
                    .options(selectinload(EventRow.entities).selectinload(EventEntityRow.entity))
                    .where(EventRow.id == canonical_id, EventRow.status == "published")
                )
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        return self._event(row) if row else None

    async def evidence_for(self, event_id: UUID) -> list[Evidence]:
        try:
            async with self.sessions() as session:
                requested = await session.get(EventRow, event_id)
                canonical_id = (
                    requested.merged_into_event_id
                    if requested is not None and requested.merged_into_event_id is not None
                    else event_id
                )
                member_ids = select(EventRow.id).where(
                    or_(
                        EventRow.id == canonical_id,
                        EventRow.merged_into_event_id == canonical_id,
                    )
                )
                rows = list(
                    (
                        await session.scalars(
                            select(EvidenceRow)
                            .join(EventRow, EvidenceRow.event_id == EventRow.id)
                            .options(
                                selectinload(EvidenceRow.article_version),
                                selectinload(EvidenceRow.event),
                            )
                            .where(
                                EvidenceRow.event_id.in_(member_ids),
                            )
                        )
                    ).all()
                )
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        evidence: list[Evidence] = []
        for row in rows:
            paragraph = row.article_version.paragraphs.get(row.paragraph_id)
            if not row.quote_text or paragraph is None or row.quote_text not in paragraph:
                raise EvidenceInvalid("Evidence cannot be located in article version")
            evidence.append(
                Evidence(
                    id=row.id,
                    event_id=row.event_id,
                    article_version_id=row.article_version_id,
                    paragraph_id=row.paragraph_id,
                    quote_text=row.quote_text,
                    source_url=row.article_version.source_url,
                    title=row.article_version.title,
                    verification_status=row.verification_status,
                    source_published_at=row.article_version.published_at,
                    event_date=row.event.event_date,
                )
            )
        return evidence

    async def articles_for(self, event_id: UUID) -> list[Article]:
        evidence = await self.evidence_for(event_id)
        result: dict[UUID, Article] = {}
        for item in evidence:
            try:
                async with self.sessions() as session:
                    row = await session.get(self.article_version_model, item.article_version_id)
            except Exception as exc:
                raise RepositoryUnavailable("PostgreSQL query failed") from exc
            if row is None:
                continue
            paragraph = row.paragraphs.get(item.paragraph_id)
            if paragraph is None or item.quote_text not in paragraph:
                raise RepositoryUnavailable("Evidence cannot be located in article version")
            result[row.id] = Article(
                id=row.id,
                title=row.title,
                source_url=row.source_url,
                paragraphs=row.paragraphs,
                synthetic=False,
            )
        return list(result.values())

    @property
    def article_version_model(self) -> type[Any]:
        from .models import ArticleVersionRow

        return ArticleVersionRow

    async def stats(self) -> dict[str, object]:
        try:
            async with self.sessions() as session:
                total = int(
                    (
                        await session.scalar(
                            select(func.count())
                            .select_from(EventRow)
                            .where(EventRow.status == "published")
                        )
                    )
                    or 0
                )
                category_rows = (
                    await session.execute(
                        select(EventRow.category, func.count())
                        .where(EventRow.status == "published")
                        .group_by(EventRow.category)
                    )
                ).all()
                total_sources = int((await session.scalar(select(func.count(SourceRow.id)))) or 0)
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        return {
            "total_events": total,
            "total_sources": total_sources,
            "categories": {str(row[0]): int(row[1]) for row in category_rows},
            "scope": "global",
            "as_of": datetime.now(UTC),
            "data_revision": "postgres-live",
        }

    async def insights(self) -> dict[str, object]:
        today = datetime.now(self.timezone).date()
        statement = (
            select(EventRow)
            .options(selectinload(EventRow.entities).selectinload(EventEntityRow.entity))
            .where(
                EventRow.status == "published",
                EventRow.date_precision == "day",
                EventRow.event_date == today,
            )
            .order_by(EventRow.importance.desc(), EventRow.id.desc())
            .limit(3)
        )
        try:
            async with self.sessions() as session:
                rows = list((await session.scalars(statement)).all())
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        return {
            "headlines": [self._event(row) for row in rows],
            "tags": [],
            "scope": "global",
            "as_of": datetime.now(UTC),
            "data_revision": "postgres-live",
        }

    async def insight_summary(self, filters: Filters) -> InsightsSnapshot:
        clauses = self._filters(filters)
        try:
            async with self.sessions() as session, session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                total = int(
                    (
                        await session.scalar(
                            select(func.count()).select_from(EventRow).where(*clauses)
                        )
                    )
                    or 0
                )
                daily_rows = (
                    await session.execute(
                        select(EventRow.event_date, func.count())
                        .where(*clauses)
                        .group_by(EventRow.event_date)
                        .order_by(EventRow.event_date)
                    )
                ).all()
                category_rows = (
                    await session.execute(
                        select(EventRow.category, func.count())
                        .where(*clauses)
                        .group_by(EventRow.category)
                    )
                ).all()
                daily_category_rows = (
                    await session.execute(
                        select(EventRow.event_date, EventRow.category, func.count())
                        .where(*clauses)
                        .group_by(EventRow.event_date, EventRow.category)
                        .order_by(EventRow.event_date, EventRow.category)
                    )
                ).all()
            return InsightsSnapshot(
                total_events=total,
                daily={row[0]: int(row[1]) for row in daily_rows},
                categories={Category(str(row[0])): int(row[1]) for row in category_rows},
                daily_categories={
                    (row[0], Category(str(row[1]))): int(row[2])
                    for row in daily_category_rows
                },
                as_of=datetime.now(UTC),
                data_revision="postgres-live",
            )
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc

    async def sources(self) -> list[dict[str, object]]:
        try:
            async with self.sessions() as session:
                rows = list((await session.scalars(select(SourceRow))).all())
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        return [
            {
                "id": str(row.id),
                "name": row.name,
                "feed_url": row.feed_url,
                "enabled": row.enabled,
                "health": row.health,
                "last_success_at": row.last_success_at,
                "consecutive_failures": row.consecutive_failures,
            }
            for row in rows
        ]

    async def ready(self) -> bool:
        try:
            async with self.sessions() as session:
                revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
                vector = await session.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
                )
            return revision == SCHEMA_REVISION and bool(vector)
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL readiness check failed") from exc
