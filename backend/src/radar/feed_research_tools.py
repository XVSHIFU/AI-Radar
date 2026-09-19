"""Research over the same article/curated-item projection as the public feed."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select

from .feed_repository import article_evidence, public_feed_query
from .research_guard import ResearchRejected, canonical
from .research_tools import ResearchTools
from .schemas import Category, Filters


class FeedResearchTools(ResearchTools):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._feed = public_feed_query(self.filters, str(self.repository.timezone))

    def _metadata(self) -> dict[str, Any]:
        return {
            **super()._metadata(),
            "coverage": "recorded_articles_and_curated_events",
            "date_basis": "source_publication_or_collection_date",
        }

    async def _count(self, *extra: Any) -> int:
        return int(
            await self.session.scalar(select(func.count()).select_from(self._feed).where(*extra))
            or 0
        )

    async def _search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args["query"].strip().lower()
        extra = []
        if query:
            extra.append(
                or_(
                    func.lower(self._feed.c.title).contains(query, autoescape=True),
                    func.lower(self._feed.c.excerpt).contains(query, autoescape=True),
                )
            )
        fingerprint = canonical({"query": query, "sort": args["sort"]})
        offset = 0
        if args["cursor"]:
            previous = self._cursors.get(args["cursor"])
            if previous is None or previous[0] != fingerprint:
                raise ResearchRejected("INVALID_ARGUMENT")
            offset = previous[1]
        order = [self._feed.c.display_date.desc().nulls_last(), self._feed.c.id.desc()]
        if args["sort"] == "importance":
            order.insert(0, self._feed.c.importance.desc().nulls_last())
        records = (
            (
                await self.session.execute(
                    select(self._feed).where(*extra).order_by(*order).offset(offset).limit(6)
                )
            )
            .mappings()
            .all()
        )
        rows = []
        for record in records:
            row = json.loads(json.dumps(dict(record), default=str))
            row["summary_truncated"] = len(row.get("excerpt") or "") > 500
            row["excerpt"] = (row.get("excerpt") or "")[:500]
            rows.append(row)
            self.retrieved_events.add(row["id"])
        total = await self._count(*extra)
        cursor = None
        if offset + len(rows) < total:
            cursor = secrets.token_urlsafe(24)
            self._cursors[cursor] = (fingerprint, offset + len(rows))
        return {
            **self._metadata(),
            "scope_total": await self._count(),
            "matched_total": total,
            "returned_count": len(rows),
            "next_cursor": cursor,
            "events": rows,
            "retrieval_mode": "keyword",
            "complete": offset == 0 and cursor is None,
        }

    def _dataset(
        self, rows: list[dict[str, Any]], fields: list[str], **extra: Any
    ) -> dict[str, Any]:
        return super()._dataset(rows, fields, unit="items", **extra)

    async def _aggregate(self, args: dict[str, Any]) -> dict[str, Any]:
        dimension = args["dimension"]
        groups, fields, extra = [], [], []
        if dimension != "category":
            groups.append(
                func.to_char(
                    self._feed.c.display_date,
                    "YYYY-MM" if args["granularity"] == "month" else "YYYY-MM-DD",
                )
            )
            fields.append("date")
            extra.append(self._feed.c.display_date.is_not(None))
        if dimension != "date":
            groups.append(func.coalesce(self._feed.c.category, "unclassified"))
            fields.append("category")
        records = (
            await self.session.execute(
                select(*groups, func.count())
                .select_from(self._feed)
                .where(*extra)
                .group_by(*groups)
                .order_by(*groups)
                .limit(10001)
            )
        ).all()
        rows = [dict(zip([*fields, "count"], row, strict=True)) for row in records]
        if dimension == "category":
            counts = {row["category"]: row["count"] for row in rows}
            rows = [
                {"category": key, "count": counts.get(key, 0)}
                for key in dict.fromkeys([*(category.value for category in Category), "unclassified"])
            ]
        total, included = await self._count(), await self._count(*extra)
        articles = await self._count(self._feed.c.content_kind == "article")
        return self._dataset(
            rows,
            [*fields, "count"],
            total_items=total,
            total_articles=articles,
            total_curated_events=total - articles,
            included_items=included,
            excluded_unknown_dates=total - included,
            date_basis="source_publication_or_collection_date",
            zero_buckets="included" if dimension == "category" else "omitted",
        )

    async def _compare(self, args: dict[str, Any]) -> dict[str, Any]:
        periods = []
        rows = []
        for name in ("first", "second"):
            start, end = (date.fromisoformat(args[name][key]) for key in ("from", "to"))
            if start > end:
                raise ResearchRejected("INVALID_ARGUMENT")
            if (self.filters.date_from and start < self.filters.date_from) or (
                self.filters.date_to and end > self.filters.date_to
            ):
                raise ResearchRejected("SCOPE_CHANGE_REQUIRED")
            periods.append((start, end))
            count = await self._count(
                self._feed.c.display_date >= start, self._feed.c.display_date <= end
            )
            days = (end - start).days + 1
            rows.append(
                {
                    "period": name,
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "days": days,
                    "count": count,
                    "daily_average": count / days,
                }
            )
        baseline, current = rows[0]["count"], rows[1]["count"]
        return self._dataset(
            rows,
            ["period", "from", "to", "days", "count", "daily_average"],
            difference=current - baseline,
            percentage_change=None if not baseline else (current - baseline) / baseline * 100,
            zero_baseline=baseline == 0,
            unequal_duration=rows[0]["days"] != rows[1]["days"],
            overlapping=max(p[0] for p in periods) <= min(p[1] for p in periods),
            date_basis="source_publication_or_collection_date",
            coverage_gaps="not_measured",
        )

    async def _evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        ids = [UUID(value) for value in args["event_ids"]]
        records = (
            (await self.session.execute(select(self._feed).where(self._feed.c.id.in_(ids))))
            .mappings()
            .all()
        )
        if {row["id"] for row in records} != set(ids):
            raise ResearchRejected("NOT_FOUND")
        output = []
        curated = [str(row["id"]) for row in records if row["content_kind"] == "event"]
        if curated:
            legacy = ResearchTools(
                self.repository,
                self.session,
                self.guard,
                Filters(event_ids=[UUID(value) for value in curated]),
                self._skills,
                self.as_of,
                self.revision,
            )
            legacy.sources, legacy.citations = self.sources, self.citations
            legacy.retrieved_events = self.retrieved_events
            output.extend((await legacy._evidence({"event_ids": curated}))["evidence"])
        for row in records:
            if row["content_kind"] != "article":
                continue
            evidence = await article_evidence(self.session, row["id"])
            self.retrieved_events.add(str(row["id"]))
            for original in evidence[:6]:
                quote = original.quote_text[:1200]
                item = original.model_copy(
                    update={
                        "quote_text": quote,
                        "quote_hash": hashlib.sha256(quote.encode()).hexdigest(),
                    }
                )
                citation_id = str(item.id)
                index = next(
                    (
                        i
                        for i, source in self.sources.items()
                        if source.get("evidence_id") == citation_id
                    ),
                    len(self.sources) + 1,
                )
                value = item.model_dump(mode="json")
                self.citations[citation_id] = item
                self.sources[index] = {
                    **value,
                    "index": index,
                    "kind": "evidence",
                    "evidence_id": citation_id,
                    "event_id": str(row["id"]),
                    "content_kind": "article",
                    "excerpt_kind": "body_excerpt",
                    "body_available": True,
                }
                output.append({**value, "citation_id": citation_id, "citation_index": index})
            if not evidence:
                # Feed metadata is useful but is not a frozen body paragraph or verified claim.
                index = next(
                    (
                        i
                        for i, source in self.sources.items()
                        if source.get("article_id") == str(row["id"])
                    ),
                    len(self.sources) + 1,
                )
                source = {
                    "index": index,
                    "kind": "article",
                    "article_id": str(row["id"]),
                    "title": row["title"],
                    "source_url": row["source_url"],
                    "quote_text": (row["excerpt"] or "")[:2000],
                    "excerpt_kind": "feed_excerpt",
                    "body_available": False,
                    "verification_status": "unverified",
                }
                self.sources[index] = source
                output.append({**source, "citation_index": index})
        if len(self.sources) > 60:
            raise ResearchRejected("RESOURCE_LIMIT")
        return {**self._metadata(), "evidence": output, "complete": True}
