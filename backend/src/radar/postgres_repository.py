from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, exists, func, insert, literal, or_, select, text
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased, selectinload

from .cursor import decode_snapshot_cursor, encode_snapshot_cursor, filters_fingerprint
from .db_schema import SCHEMA_REVISION
from .hybrid import hybrid_search
from .models import (
    EmbeddingProfileRow,
    EntityAliasRow,
    EntityRow,
    EventEntityRow,
    EventRow,
    EvidenceRow,
    RetrievalSnapshotRow,
    SourceRow,
)
from .normalize import normalize_text
from .queryplanner import EntityResolution, ResolvedEntity, resolve_confirmed_entities
from .repository import (
    EvidenceInvalid,
    InsightsSnapshot,
    InvalidCursor,
    Page,
    RepositoryUnavailable,
    SearchPage,
)
from .retrieval import EmbeddingProvider, checked_query_embedding, search_document
from .schemas import Article, Category, Event, Evidence, Filters


class PostgresRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        cursor_secret: str,
        timezone: str = "Asia/Shanghai",
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.sessions = sessions
        self.embedding_provider = embedding_provider
        self.cursor_secret = cursor_secret
        self.timezone = ZoneInfo(timezone)

    def _filters(self, filters: Filters) -> list[Any]:
        clauses: list[Any] = [EventRow.status == "published"]
        member = aliased(EventRow)
        member_event_ids = (
            select(member.id)
            .where(
                or_(
                    member.id == EventRow.id,
                    member.merged_into_event_id == EventRow.id,
                )
            )
            .correlate(EventRow)
        )
        if filters.event_ids:
            clauses.append(
                or_(
                    EventRow.id.in_(filters.event_ids),
                    exists().where(
                        member.merged_into_event_id == EventRow.id,
                        member.id.in_(filters.event_ids),
                    ),
                )
            )
        if filters.category:
            clauses.append(EventRow.category == filters.category.value)
        if filters.date_from or filters.date_to:
            clauses.extend(
                (
                    EventRow.date_basis.in_(("explicit_body", "official_publication")),
                    EventRow.date_conflict.is_(False),
                )
            )
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
                    EventEntityRow.event_id.in_(member_event_ids),
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
                        EventEntityRow.event_id.in_(member_event_ids),
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

    def _snapshot_item_json(self) -> Any:
        """Frozen event projection; keep in sync with the public Event schema."""
        member = aliased(EventRow)
        member_ids = (
            select(member.id)
            .where(or_(member.id == EventRow.id, member.merged_into_event_id == EventRow.id))
            .correlate(EventRow)
        )
        merged_ids = (
            select(
                func.coalesce(
                    func.jsonb_agg(aggregate_order_by(member.id, member.id)),
                    text("'[]'::jsonb"),
                )
            )
            .where(member.merged_into_event_id == EventRow.id)
            .correlate(EventRow)
            .scalar_subquery()
        )
        entity_names = (
            select(
                func.coalesce(
                    func.jsonb_agg(
                        aggregate_order_by(
                            EntityRow.canonical_name.distinct(), EntityRow.canonical_name
                        )
                    ),
                    text("'[]'::jsonb"),
                )
            )
            .select_from(EventEntityRow)
            .join(EntityRow, EntityRow.id == EventEntityRow.entity_id)
            .where(EventEntityRow.event_id.in_(member_ids))
            .correlate(EventRow)
            .scalar_subquery()
        )
        return func.jsonb_build_object(
            "id",
            EventRow.id,
            "title_zh",
            EventRow.title_zh,
            "summary_zh",
            EventRow.summary_zh,
            "category",
            EventRow.category,
            "importance",
            EventRow.importance,
            "event_date",
            EventRow.event_date,
            "date_precision",
            EventRow.date_precision,
            "source_count",
            EventRow.source_count,
            "evidence_count",
            EventRow.evidence_count,
            "entities",
            entity_names,
            "content_version",
            EventRow.content_version,
            "date_basis",
            EventRow.date_basis,
            "date_conflict",
            EventRow.date_conflict,
            "canonical_id",
            EventRow.id,
            "merged_source_event_ids",
            merged_ids,
        )

    async def list_events(self, filters: Filters, limit: int, cursor: str | None) -> Page:
        now = datetime.now(UTC)
        try:
            async with self.sessions() as session, session.begin():
                if cursor:
                    snapshot_id, offset = decode_snapshot_cursor(
                        cursor, filters, self.cursor_secret
                    )
                    snapshot = (
                        await session.execute(
                            select(
                                RetrievalSnapshotRow.total,
                                RetrievalSnapshotRow.created_at,
                                RetrievalSnapshotRow.expires_at,
                                RetrievalSnapshotRow.data_revision,
                            ).where(RetrievalSnapshotRow.id == snapshot_id)
                        )
                    ).one_or_none()
                    if snapshot is None or snapshot.expires_at <= now:
                        raise InvalidCursor("cursor snapshot has expired")
                    total = snapshot.total
                    as_of = snapshot.created_at
                    revision = snapshot.data_revision
                else:
                    await session.execute(
                        text(
                            "DELETE FROM retrieval_snapshots WHERE expires_at <= :now OR id IN "
                            "(SELECT id FROM retrieval_snapshots ORDER BY created_at DESC, id DESC "
                            "OFFSET 999)"
                        ),
                        {"now": now},
                    )
                    revision = int(
                        await session.scalar(
                            text(
                                "SELECT revision FROM retrieval_data_revision "
                                "WHERE singleton FOR SHARE"
                            )
                        )
                    )
                    fingerprint = filters_fingerprint(filters)
                    await session.execute(
                        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                        {"key": f"snapshot:{fingerprint}:{revision}"},
                    )
                    existing = (
                        await session.execute(
                            select(
                                RetrievalSnapshotRow.id,
                                RetrievalSnapshotRow.total,
                                RetrievalSnapshotRow.created_at,
                            ).where(
                                RetrievalSnapshotRow.filters_hash == fingerprint,
                                RetrievalSnapshotRow.data_revision == revision,
                                RetrievalSnapshotRow.expires_at > now,
                            )
                        )
                    ).one_or_none()
                    if existing is not None:
                        snapshot_id = existing.id
                        total = existing.total
                        as_of = existing.created_at
                    else:
                        snapshot_id = uuid4()
                        as_of = now
                        item = self._snapshot_item_json()
                        ordered_items = func.coalesce(
                            func.jsonb_agg(
                                aggregate_order_by(
                                    item,
                                    EventRow.event_date.desc().nulls_last(),
                                    EventRow.id.desc(),
                                )
                            ),
                            text("'[]'::jsonb"),
                        )
                        source = select(
                            literal(snapshot_id),
                            literal(fingerprint),
                            literal(revision),
                            ordered_items,
                            func.count(),
                            literal(as_of),
                            literal(as_of + timedelta(minutes=15)),
                        ).where(*self._filters(filters))
                        await session.execute(
                            insert(RetrievalSnapshotRow).from_select(
                                [
                                    "id",
                                    "filters_hash",
                                    "data_revision",
                                    "items",
                                    "total",
                                    "created_at",
                                    "expires_at",
                                ],
                                source,
                            )
                        )
                        total = int(
                            await session.scalar(
                                select(RetrievalSnapshotRow.total).where(
                                    RetrievalSnapshotRow.id == snapshot_id
                                )
                            )
                        )
                    offset = 0
                rows = await session.execute(
                    text(
                        "SELECT entry.value FROM retrieval_snapshots s, "
                        "LATERAL jsonb_array_elements(s.items) WITH ORDINALITY "
                        "AS entry(value, ordinal) WHERE s.id=:snapshot_id "
                        "AND entry.ordinal > :offset AND entry.ordinal <= :end "
                        "ORDER BY entry.ordinal"
                    ),
                    {"snapshot_id": snapshot_id, "offset": offset, "end": offset + limit},
                )
        except InvalidCursor:
            raise
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        page_items = [Event.model_validate(row[0]) for row in rows]
        next_offset = offset + len(page_items)
        next_cursor = (
            encode_snapshot_cursor(snapshot_id, next_offset, filters, self.cursor_secret)
            if next_offset < total
            else None
        )
        return Page(
            page_items,
            total,
            next_cursor,
            as_of,
            f"postgres-snapshot-v2:{revision}:{snapshot_id}",
        )

    async def search_events(self, filters: Filters, limit: int) -> SearchPage:
        if not filters.q:
            raise ValueError("search query is required")
        hard_filters = filters.model_copy(update={"q": None})
        now = datetime.now(UTC)
        try:
            async with self.sessions() as session, session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                revision = await session.scalar(
                    text("SELECT revision FROM retrieval_data_revision WHERE singleton")
                )
                now = (await session.execute(select(func.transaction_timestamp()))).scalar_one()
                scope_uuid_ids = list(
                    (
                        await session.scalars(
                            select(EventRow.id).where(*self._filters(hard_filters))
                        )
                    ).all()
                )
                scope_ids = [str(event_id) for event_id in scope_uuid_ids]

                async def keyword(
                    query: str, allowed: Sequence[str], candidate_limit: int
                ) -> list[str]:
                    if not allowed:
                        return []
                    query_document = search_document(query)
                    statement = (
                        select(EventRow.id)
                        .where(
                            *self._filters(hard_filters),
                            or_(
                                EventRow.search_vector.op("@@")(
                                    func.plainto_tsquery("simple", query_document)
                                ),
                                EventRow.title_zh.ilike(f"%{query}%"),
                                EventRow.summary_zh.ilike(f"%{query}%"),
                            ),
                        )
                        .order_by(
                            func.ts_rank(
                                EventRow.search_vector,
                                func.plainto_tsquery("simple", query_document),
                            ).desc(),
                            EventRow.event_date.desc().nulls_last(),
                            EventRow.id.desc(),
                        )
                        .limit(candidate_limit)
                    )
                    return [str(item) for item in (await session.scalars(statement)).all()]

                semantic_retriever = None
                profile_label = None
                if self.embedding_provider is not None:
                    provider = self.embedding_provider
                    profile = provider.profile
                    active = await session.scalar(
                        select(EmbeddingProfileRow).where(EmbeddingProfileRow.active.is_(True))
                    )
                    if active is not None and (
                        active.provider,
                        active.model_id,
                        active.revision,
                        active.dimension,
                        active.normalize,
                        active.input_template_version,
                    ) == (
                        profile.provider,
                        profile.model_id,
                        profile.revision,
                        profile.dimension,
                        profile.normalize,
                        profile.input_template_version,
                    ):
                        profile_label = profile.fingerprint

                        async def semantic_query(
                            query: str, allowed: Sequence[str], candidate_limit: int
                        ) -> list[str]:
                            vector = await checked_query_embedding(provider, query)
                            rendered = "[" + ",".join(str(item) for item in vector) + "]"
                            rows = await session.execute(
                                text(
                                    "SELECT ee.event_id::text FROM event_embeddings_v1 ee "
                                    "JOIN events e ON e.id=ee.event_id "
                                    "WHERE ee.profile_id=:profile_id AND ee.status='ready' "
                                    "AND ee.event_content_version=e.content_version "
                                    "AND ee.event_id = ANY(CAST(:allowed AS uuid[])) "
                                    "ORDER BY ee.embedding <=> CAST(:embedding AS vector) "
                                    "LIMIT :limit"
                                ),
                                {
                                    "profile_id": active.id,
                                    "allowed": [UUID(item) for item in allowed],
                                    "embedding": rendered,
                                    "limit": candidate_limit,
                                },
                            )
                            return [str(row[0]) for row in rows]

                        semantic_retriever = semantic_query

                result = await hybrid_search(filters.q, scope_ids, keyword, semantic_retriever)
                ranked_ids = [UUID(item) for item in result.ranked_ids[:limit]]
                ranked_rows = (
                    await session.execute(
                        select(EventRow.id, self._snapshot_item_json()).where(
                            EventRow.id.in_(ranked_ids), *self._filters(hard_filters)
                        )
                    )
                ).all()
                by_id = {row[0]: Event.model_validate(row[1]) for row in ranked_rows}
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL search failed") from exc
        return SearchPage(
            items=[by_id[event_id] for event_id in ranked_ids],
            scope_total=len(scope_ids),
            keyword_count=result.keyword_count,
            semantic_count=result.semantic_count,
            retrieval_mode=result.retrieval_mode,
            degraded_reason=result.degraded_reason,
            embedding_profile=profile_label,
            as_of=now,
            data_revision=f"retrieval-v1:cjk-bigram-v1:{revision}",
        )

    async def event(self, event_id: UUID) -> Event | None:
        requested = aliased(EventRow)
        canonical_id = (
            select(func.coalesce(requested.merged_into_event_id, requested.id))
            .where(requested.id == event_id)
            .scalar_subquery()
        )
        try:
            async with self.sessions() as session:
                row = await session.scalar(
                    select(self._snapshot_item_json())
                    .select_from(EventRow)
                    .where(EventRow.id == canonical_id, EventRow.status == "published")
                )
        except Exception as exc:
            raise RepositoryUnavailable("PostgreSQL query failed") from exc
        return Event.model_validate(row) if row is not None else None

    async def evidence_for(self, event_id: UUID) -> list[Evidence]:
        try:
            async with self.sessions() as session:
                requested = await session.get(EventRow, event_id)
                canonical_id = (
                    requested.merged_into_event_id
                    if requested is not None and requested.merged_into_event_id is not None
                    else event_id
                )
                canonical = await session.get(EventRow, canonical_id)
                if canonical is None or canonical.status != "published":
                    return []
                member_ids = select(EventRow.id).where(
                    or_(
                        EventRow.id == canonical_id,
                        and_(
                            EventRow.merged_into_event_id == canonical_id,
                            EventRow.status == "merged",
                        ),
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
                    canonical_event_id=canonical_id,
                    claim_key=row.claim_key,
                    claim_text=row.claim_text,
                    quote_hash=row.quote_hash,
                    support_type=row.support_type,
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
            select(self._snapshot_item_json())
            .select_from(EventRow)
            .where(
                EventRow.status == "published",
                EventRow.date_precision == "day",
                EventRow.event_date == today,
                EventRow.date_basis.in_(("explicit_body", "official_publication")),
                EventRow.date_conflict.is_(False),
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
            "headlines": [Event.model_validate(row) for row in rows],
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
                    (row[0], Category(str(row[1]))): int(row[2]) for row in daily_category_rows
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
