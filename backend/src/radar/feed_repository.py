"""SQL projection shared by public feed and optional research tools."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import (
    Date,
    Integer,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    text,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

from .cursor import decode_snapshot_cursor, encode_snapshot_cursor, filters_fingerprint
from .models import (
    ArticleRow,
    ArticleVersionRow,
    EntityAliasRow,
    EventArticleRow,
    EventEntityRow,
    EventRow,
    RetrievalSnapshotRow,
    SourceRow,
)
from .normalize import normalize_text
from .repository import InvalidCursor, RepositoryUnavailable
from .schemas import Category, Evidence, Filters


def _like_term(value: str) -> str:
    escaped = normalize_text(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def public_feed_query(
    filters: Filters, timezone: str = "Asia/Shanghai", unclassified: bool = False
) -> Subquery:
    """Return one row per public item, with truthful article provenance columns."""
    unclassified = unclassified or filters.category == Category.UNCLASSIFIED
    member = aliased(EventRow)
    linked_event = aliased(EventRow)
    linked_parent = aliased(EventRow)
    linked = exists(
        select(1)
        .select_from(EventArticleRow)
        .join(linked_event, linked_event.id == EventArticleRow.event_id)
        .outerjoin(linked_parent, linked_parent.id == linked_event.merged_into_event_id)
        .where(
            EventArticleRow.article_id == ArticleRow.id,
            or_(linked_event.status == "published", linked_parent.status == "published"),
        )
    )
    primary_article = (
        select(ArticleRow.canonical_url)
        .join(EventArticleRow, EventArticleRow.article_id == ArticleRow.id)
        .where(EventArticleRow.event_id == EventRow.id)
        .order_by(EventArticleRow.is_primary.desc(), ArticleRow.id)
        .limit(1)
        .correlate(EventRow)
        .scalar_subquery()
    )
    primary_source = (
        select(SourceRow.name)
        .join(ArticleRow, ArticleRow.source_id == SourceRow.id)
        .join(EventArticleRow, EventArticleRow.article_id == ArticleRow.id)
        .where(EventArticleRow.event_id == EventRow.id)
        .order_by(EventArticleRow.is_primary.desc(), ArticleRow.id)
        .limit(1)
        .correlate(EventRow)
        .scalar_subquery()
    )
    primary_publication = (
        select(func.coalesce(ArticleRow.published_at, ArticleVersionRow.published_at))
        .join(EventArticleRow, EventArticleRow.article_id == ArticleRow.id)
        .outerjoin(ArticleVersionRow, ArticleVersionRow.article_id == ArticleRow.id)
        .where(EventArticleRow.event_id == EventRow.id)
        .order_by(
            EventArticleRow.is_primary.desc(), ArticleVersionRow.fetched_at.desc().nulls_last()
        )
        .limit(1)
        .correlate(EventRow)
        .scalar_subquery()
    )
    event_display = func.coalesce(
        cast(func.timezone(timezone, primary_publication), Date),
        cast(func.timezone(timezone, EventRow.created_at), Date),
    )
    no_uuid = cast(literal(None), ArticleRow.id.type)
    event_columns = select(
        EventRow.id.label("id"),
        literal("event").label("content_kind"),
        EventRow.title_zh.label("title"),
        EventRow.summary_zh.label("excerpt"),
        EventRow.category.label("category"),
        EventRow.importance.label("importance"),
        primary_publication.label("published_at"),
        EventRow.created_at.label("ingested_at"),
        event_display.label("display_date"),
        primary_source.label("source_name"),
        primary_article.label("source_url"),
        no_uuid.label("article_version_id"),
        literal(False).label("body_available"),
        literal("curated_summary").label("excerpt_kind"),
    )
    event_clauses: list[Any] = [EventRow.status == "published"]
    if filters.event_ids:
        event_clauses.append(
            or_(
                EventRow.id.in_(filters.event_ids),
                exists(
                    select(1).where(
                        member.merged_into_event_id == EventRow.id, member.id.in_(filters.event_ids)
                    )
                ),
            )
        )
    if unclassified:
        event_clauses.append(literal(False))
    elif filters.category:
        event_clauses.append(EventRow.category == filters.category.value)
    if filters.date_from:
        event_clauses.append(event_display >= filters.date_from)
    if filters.date_to:
        event_clauses.append(event_display <= filters.date_to)
    if filters.min_importance:
        event_clauses.append(EventRow.importance >= filters.min_importance)
    if filters.q:
        term = _like_term(filters.q)
        event_clauses.append(
            or_(
                EventRow.title_zh.ilike(term, escape="\\"),
                EventRow.summary_zh.ilike(term, escape="\\"),
            )
        )
    if filters.entity_ids:
        members = (
            select(member.id)
            .where(or_(member.id == EventRow.id, member.merged_into_event_id == EventRow.id))
            .correlate(EventRow)
        )
        count = (
            select(func.count(func.distinct(EventEntityRow.entity_id)))
            .where(
                EventEntityRow.event_id.in_(members),
                EventEntityRow.entity_id.in_(filters.entity_ids),
                EventEntityRow.role.in_(("subject", "product")),
            )
            .scalar_subquery()
        )
        event_clauses.append(
            count >= (len(filters.entity_ids) if filters.entity_match == "all" else 1)
        )
    event_columns = event_columns.where(*event_clauses)

    display = cast(
        func.timezone(timezone, func.coalesce(ArticleRow.published_at, ArticleRow.ingested_at)),
        Date,
    )
    article_columns = select(
        ArticleRow.id.label("id"),
        literal("article").label("content_kind"),
        ArticleRow.title.label("title"),
        ArticleRow.excerpt.label("excerpt"),
        ArticleRow.category.label("category"),
        cast(literal(None), Integer).label("importance"),
        ArticleRow.published_at.label("published_at"),
        ArticleRow.ingested_at.label("ingested_at"),
        display.label("display_date"),
        SourceRow.name.label("source_name"),
        ArticleRow.canonical_url.label("source_url"),
        ArticleRow.current_version_id.label("article_version_id"),
        ArticleRow.current_version_id.is_not(None).label("body_available"),
        literal("feed_excerpt").label("excerpt_kind"),
    ).join(SourceRow, SourceRow.id == ArticleRow.source_id)
    article_clauses: list[Any] = [
        ArticleRow.status == "published",
        ArticleRow.duplicate_of_id.is_(None),
        ~linked,
    ]
    if filters.event_ids:
        article_clauses.append(ArticleRow.id.in_(filters.event_ids))
    if unclassified:
        article_clauses.append(ArticleRow.category.is_(None))
    elif filters.category:
        article_clauses.append(ArticleRow.category == filters.category.value)
    if filters.date_from:
        article_clauses.append(display >= filters.date_from)
    if filters.date_to:
        article_clauses.append(display <= filters.date_to)
    if filters.min_importance:
        article_clauses.append(literal(False))
    if filters.q:
        term = _like_term(filters.q)
        article_clauses.append(
            or_(
                ArticleRow.title.ilike(term, escape="\\"),
                ArticleRow.excerpt.ilike(term, escape="\\"),
            )
        )
    if filters.entity_ids:
        alias_match = exists(
            select(1).where(
                EntityAliasRow.entity_id.in_(filters.entity_ids),
                or_(
                    ArticleRow.title.ilike(func.concat("%", EntityAliasRow.normalized_alias, "%")),
                    ArticleRow.excerpt.ilike(
                        func.concat("%", EntityAliasRow.normalized_alias, "%")
                    ),
                ),
            )
        )
        if filters.entity_match == "all":
            alias_count = (
                select(func.count(func.distinct(EntityAliasRow.entity_id)))
                .where(
                    EntityAliasRow.entity_id.in_(filters.entity_ids),
                    or_(
                        ArticleRow.title.ilike(
                            func.concat("%", EntityAliasRow.normalized_alias, "%")
                        ),
                        ArticleRow.excerpt.ilike(
                            func.concat("%", EntityAliasRow.normalized_alias, "%")
                        ),
                    ),
                )
                .scalar_subquery()
            )
            article_clauses.append(alias_count >= len(filters.entity_ids))
        else:
            article_clauses.append(alias_match)
    article_columns = article_columns.where(*article_clauses)
    return union_all(event_columns, article_columns).subquery("public_feed")


def _json_row(row: Any) -> dict[str, Any]:
    item = dict(row._mapping)
    for key in ("id", "article_version_id"):
        if item.get(key) is not None:
            item[key] = str(item[key])
    for key in ("published_at", "ingested_at", "display_date"):
        if item.get(key) is not None:
            item[key] = item[key].isoformat()
    return item


async def article_evidence(session: AsyncSession, article_id: UUID) -> list[Evidence]:
    article = await session.get(ArticleRow, article_id)
    if article is None or article.current_version_id is None:
        return []
    version = await session.get(ArticleVersionRow, article.current_version_id)
    if version is None:
        return []
    return [
        Evidence(
            id=uuid5(NAMESPACE_URL, f"article:{version.id}:{paragraph_id}"),
            event_id=article.id,
            article_version_id=version.id,
            paragraph_id=paragraph_id,
            quote_text=paragraph,
            source_url=version.source_url,
            title=version.title or article.title or "",
            verification_status="unverified",
            source_published_at=article.published_at,
            event_date=None,
            canonical_event_id=article.id,
        )
        for paragraph_id, paragraph in version.paragraphs.items()
    ]


class FeedRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        cursor_secret: str,
        timezone: str = "Asia/Shanghai",
    ):
        self.sessions = sessions
        self.cursor_secret = cursor_secret
        self.timezone = timezone

    async def list(
        self, filters: Filters, limit: int, cursor: str | None, unclassified: bool = False
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        fingerprint = hashlib.sha256(
            (
                "feed:" + filters_fingerprint(filters) + (":unclassified" if unclassified else "")
            ).encode()
        ).hexdigest()
        try:
            async with self.sessions() as session, session.begin():
                if cursor:
                    snapshot_id, offset = decode_snapshot_cursor(
                        cursor, filters, self.cursor_secret
                    )
                    snapshot = await session.get(RetrievalSnapshotRow, snapshot_id)
                    if (
                        snapshot is None
                        or snapshot.expires_at <= now
                        or snapshot.filters_hash != fingerprint
                    ):
                        raise InvalidCursor("feed cursor snapshot has expired")
                else:
                    revision = int(
                        await session.scalar(
                            text(
                                "SELECT revision FROM retrieval_data_revision "
                                "WHERE singleton FOR SHARE"
                            )
                        )
                    )
                    await session.execute(
                        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                        {"key": f"feed:{fingerprint}:{revision}"},
                    )
                    snapshot = await session.scalar(
                        select(RetrievalSnapshotRow).where(
                            RetrievalSnapshotRow.filters_hash == fingerprint,
                            RetrievalSnapshotRow.data_revision == revision,
                            RetrievalSnapshotRow.expires_at > now,
                        )
                    )
                    if snapshot is None:
                        projection = public_feed_query(filters, self.timezone, unclassified)
                        result = await session.execute(
                            select(projection).order_by(
                                projection.c.display_date.desc().nulls_last(),
                                projection.c.id.desc(),
                            )
                        )
                        items = [_json_row(row) for row in result]
                        snapshot = RetrievalSnapshotRow(
                            id=uuid4(),
                            filters_hash=fingerprint,
                            items=items,
                            data_revision=revision,
                            total=len(items),
                            created_at=now,
                            expires_at=now + timedelta(minutes=15),
                        )
                        session.add(snapshot)
                        await session.flush()
                    offset = 0
                items = snapshot.items[offset : offset + limit]
                next_offset = offset + len(items)
                return {
                    "items": items,
                    "total": snapshot.total,
                    "total_relation": "eq",
                    "next_cursor": encode_snapshot_cursor(
                        snapshot.id, next_offset, filters, self.cursor_secret
                    )
                    if next_offset < snapshot.total
                    else None,
                    "as_of": snapshot.created_at,
                    "data_revision": f"postgres-feed-v1:{snapshot.data_revision}:{snapshot.id}",
                }
        except InvalidCursor:
            raise
        except Exception as exc:
            raise RepositoryUnavailable("public feed query failed") from exc

    async def detail(self, item_id: UUID) -> dict[str, Any] | None:
        async with self.sessions() as session:
            projection = public_feed_query(Filters(event_ids=[item_id]), self.timezone)
            row = (
                await session.execute(select(projection).where(projection.c.id == item_id))
            ).one_or_none()
            if row is None:
                return None
            item = _json_row(row)
            if item["content_kind"] == "article":
                article = await session.get(ArticleRow, item_id)
                version = (
                    await session.get(ArticleVersionRow, article.current_version_id)
                    if article and article.current_version_id
                    else None
                )
                item["paragraphs"] = version.paragraphs if version else {}
                item["evidence"] = [
                    e.model_dump(mode="json") for e in await article_evidence(session, item_id)
                ]
            return item

    async def stats(self) -> dict[str, Any]:
        async with self.sessions() as session:
            projection = public_feed_query(Filters(), self.timezone)
            rows = (
                await session.execute(
                    select(projection.c.content_kind, projection.c.category, func.count()).group_by(
                        projection.c.content_kind, projection.c.category
                    )
                )
            ).all()
            sources = await session.scalar(
                select(func.count()).select_from(SourceRow).where(SourceRow.enabled.is_(True))
            )
            revision = await session.scalar(
                text("SELECT revision FROM retrieval_data_revision WHERE singleton")
            )
        counts: dict[str, Any] = {
            "total_items": 0,
            "total_articles": 0,
            "total_events": 0,
            "total_sources": int(sources or 0),
            "categories": {},
        }
        for kind, category, count in rows:
            counts["total_items"] += count
            counts[f"total_{kind}s"] += count
            key = category or "unclassified"
            counts["categories"][key] = counts["categories"].get(key, 0) + count
        return {
            **counts,
            "scope": "global",
            "as_of": datetime.now(UTC),
            "data_revision": str(revision),
        }

    async def insights(self, filters: Filters, unclassified: bool = False) -> dict[str, Any]:
        async with self.sessions() as session:
            projection = public_feed_query(filters, self.timezone, unclassified)
            rows = (
                await session.execute(
                    select(
                        projection.c.display_date,
                        projection.c.category,
                        projection.c.content_kind,
                        func.count(),
                    ).group_by(
                        projection.c.display_date, projection.c.category, projection.c.content_kind
                    )
                )
            ).all()
            revision = await session.scalar(
                text("SELECT revision FROM retrieval_data_revision WHERE singleton")
            )
        daily: dict[str, int] = {}
        categories: dict[str, int] = {}
        matrix: dict[tuple[str, str], int] = {}
        article_count = event_count = 0
        for day, category, kind, count in rows:
            if kind == "article":
                article_count += count
            else:
                event_count += count
            key = category or "unclassified"
            categories[key] = categories.get(key, 0) + count
            if day is not None:
                day_key = day.isoformat()
                daily[day_key] = daily.get(day_key, 0) + count
                matrix[(day_key, key)] = matrix.get((day_key, key), 0) + count
        return {
            "total_items": article_count + event_count,
            "total_articles": article_count,
            "total_events": event_count,
            "daily": [{"date": day, "count": count} for day, count in sorted(daily.items())],
            "categories": [
                {"category": key, "count": count} for key, count in sorted(categories.items())
            ],
            "daily_categories": [
                {"date": day, "category": key, "count": count}
                for (day, key), count in sorted(matrix.items())
            ],
            "as_of": datetime.now(UTC),
            "data_revision": str(revision),
        }

    async def admin_articles(self, status: str | None, limit: int) -> dict[str, Any]:
        async with self.sessions() as session:
            clauses: list[ColumnElement[bool]] = [
                ArticleRow.status.in_(("published", "hidden"))
            ]
            if status:
                clauses.append(ArticleRow.status == status)
            total = await session.scalar(
                select(func.count()).select_from(ArticleRow).where(*clauses)
            )
            rows = (
                await session.execute(
                    select(ArticleRow, SourceRow.name)
                    .join(SourceRow, SourceRow.id == ArticleRow.source_id)
                    .where(*clauses)
                    .order_by(ArticleRow.ingested_at.desc().nulls_last(), ArticleRow.id.desc())
                    .limit(limit)
                )
            ).all()
            return {
                "items": [
                    {
                        "id": row.id,
                        "title": row.title,
                        "source_name": source_name,
                        "source_url": row.canonical_url,
                        "published_at": row.published_at,
                        "ingested_at": row.ingested_at,
                        "status": row.status,
                    }
                    for row, source_name in rows
                ],
                "total": int(total or 0),
            }

    async def set_status(self, article_id: UUID, status: str) -> dict[str, Any] | None:
        async with self.sessions() as session, session.begin():
            article = await session.scalar(
                select(ArticleRow).where(ArticleRow.id == article_id).with_for_update()
            )
            if article is None or article.status not in {"published", "hidden"}:
                return None
            article.status = status
            return {"id": article.id, "status": article.status}
