"""Research-only views over one read-only PostgreSQL snapshot.

At most two admitted runs hold a snapshot, each for at most 90 seconds. No SQL,
paths, scope IDs or connection parameters are accepted from model arguments.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from .models import EntityAliasRow, EntityRow, EventEntityRow, EventRow, EvidenceRow
from .normalize import normalize_text
from .postgres_repository import PostgresRepository
from .research_gateway import SCHEMAS
from .research_guard import ResearchGuard, ResearchRejected, canonical
from .schemas import Category, Evidence, Filters

SKILL_NAMES = ("explain-event", "compare-periods", "verify-evidence")


def load_research_skills(packaged_root: Path) -> dict[str, dict[str, str]]:
    """Call at startup with a deployment-owned path, never a tool parameter."""
    result = {}
    root = packaged_root.resolve(strict=True)
    for name in SKILL_NAMES:
        path = root / "skills" / name / "SKILL.md"
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("skill must be a packaged file")
        data = path.read_bytes()
        if len(data) > 8192:
            raise ValueError("skill size limit")
        result[name] = {
            "name": name,
            "body": data.decode("utf-8"),
            "version": hashlib.sha256(data).hexdigest(),
        }
    return result


@asynccontextmanager
async def research_scope(
    repository: PostgresRepository,
    guard: ResearchGuard,
    filters: Filters,
    skills: Mapping[str, dict[str, str]],
) -> AsyncIterator[ResearchTools]:
    guard.check(guard.capability)
    async with repository.sessions() as session, session.begin():
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        await session.execute(text("SET LOCAL statement_timeout = '10s'"))
        await session.execute(text("SET LOCAL idle_in_transaction_session_timeout = '95s'"))
        as_of = await session.scalar(select(func.transaction_timestamp()))
        snapshot = await session.scalar(text("SELECT pg_current_snapshot()::text"))
        toolset = ResearchTools(
            repository, session, guard, filters, skills, str(as_of), str(snapshot)
        )
        try:
            yield toolset
        finally:
            toolset._closed = True
            toolset._datasets.clear()
            toolset._cursors.clear()
            toolset.citations.clear()
            toolset.sources.clear()


class ResearchTools:
    def __init__(
        self,
        repository: PostgresRepository,
        session: AsyncSession,
        guard: ResearchGuard,
        filters: Filters,
        skills: Mapping[str, dict[str, str]],
        as_of: str,
        revision: str,
    ) -> None:
        self.repository = repository
        self.session = session
        self.guard = guard
        self.filters = filters.model_copy(deep=True)
        self._clauses = repository._filters(self.filters)
        self.scope_id = uuid4()
        self.as_of = as_of
        self.revision = revision
        self._skills = json.loads(canonical(skills))
        self._datasets: dict[str, dict[str, Any]] = {}
        self._cursors: dict[str, tuple[str, int]] = {}
        self.citations: dict[str, Evidence] = {}
        self.sources: dict[int, dict[str, Any]] = {}
        self.retrieved_events: set[str] = set()
        self._closed = False

    def _check(self) -> None:
        self.guard.check(self.guard.capability)
        if self._closed:
            raise ResearchRejected("RUN_EXPIRED")

    def _metadata(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "data_revision": self.revision,
            "scope_id": str(self.scope_id),
            "coverage": "recorded_events_only",
            "timezone": str(self.repository.timezone),
        }

    async def execute(self, name: str, arguments: dict[str, Any]) -> object:
        self._check()
        schema = SCHEMAS.get(name)
        if schema is None:
            raise ResearchRejected("TOOL_UNAVAILABLE")
        args = schema.model_validate(arguments).model_dump(by_alias=True)
        if name == "search_events":
            result = await self._search(args)
        elif name == "aggregate_events":
            result = await self._aggregate(args)
        elif name == "compare_periods":
            result = await self._compare(args)
        elif name == "get_event_evidence":
            result = await self._evidence(args)
        elif name == "resolve_entities":
            result = await self._resolve(args)
        elif name == "build_chart":
            result = self._chart(args)
        else:
            skill = self._skills.get(args["name"])
            if skill is None:
                raise ResearchRejected("TOOL_UNAVAILABLE")
            result = skill
        self._check()
        if len(canonical(result).encode("utf-8")) > 32768:
            raise ResearchRejected("RESOURCE_LIMIT")
        return json.loads(canonical(result))

    async def _count(self, *extra: Any) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(EventRow).where(*self._clauses, *extra)
            )
            or 0
        )

    def _members(self) -> Any:
        canonical_ids = select(EventRow.id).where(*self._clauses)
        member = aliased(EventRow)
        return select(member.id).where(
            or_(
                member.id.in_(canonical_ids),
                and_(member.status == "merged", member.merged_into_event_id.in_(canonical_ids)),
            )
        )

    async def _resolve(self, args: dict[str, Any]) -> dict[str, Any]:
        name = normalize_text(args["name"])
        scoped_entity_ids = select(EventEntityRow.entity_id).where(
            EventEntityRow.event_id.in_(self._members()),
            EventEntityRow.role.in_(("subject", "product")),
        )
        aliases = select(EntityAliasRow.entity_id).where(EntityAliasRow.normalized_alias == name)
        rows = (
            await self.session.execute(
                select(EntityRow.id, EntityRow.canonical_name)
                .where(
                    EntityRow.id.in_(scoped_entity_ids),
                    or_(func.lower(EntityRow.canonical_name) == name, EntityRow.id.in_(aliases)),
                )
                .order_by(EntityRow.canonical_name)
                .limit(11)
            )
        ).all()
        if len(rows) > 10:
            raise ResearchRejected("RESOURCE_LIMIT")
        return {
            **self._metadata(),
            "ambiguous": len(rows) > 1,
            "matches": [{"entity_id": str(row[0]), "name": row[1]} for row in rows],
        }

    async def _search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = normalize_text(args["query"])
        extra: list[Any] = []
        if query:
            extra.append(
                or_(
                    func.lower(EventRow.title_zh).contains(query, autoescape=True),
                    func.lower(EventRow.summary_zh).contains(query, autoescape=True),
                )
            )
        fingerprint = canonical({"query": query, "sort": args["sort"]})
        offset = 0
        if args["cursor"]:
            previous = self._cursors.get(args["cursor"])
            if previous is None or previous[0] != fingerprint:
                raise ResearchRejected("INVALID_ARGUMENT")
            offset = previous[1]
        total = await self._count(*extra)
        order: list[Any] = [EventRow.event_date.desc().nulls_last(), EventRow.id.desc()]
        if args["sort"] == "importance":
            order.insert(0, EventRow.importance.desc())
        rows = list(
            (
                await self.session.scalars(
                    select(self.repository._snapshot_item_json())
                    .where(*self._clauses, *extra)
                    .order_by(*order)
                    .offset(offset)
                    .limit(6)
                )
            ).all()
        )
        cursor = None
        if offset + len(rows) < total:
            cursor = secrets.token_urlsafe(24)
            self._cursors[cursor] = (fingerprint, offset + len(rows))
        for row in rows:
            self.retrieved_events.add(row["id"])
            row["summary_truncated"] = len(row["summary_zh"]) > 500
            row["summary_zh"] = row["summary_zh"][:500]
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

    @staticmethod
    def _verified_date() -> tuple[Any, ...]:
        return (
            EventRow.date_precision == "day",
            EventRow.event_date.is_not(None),
            EventRow.date_basis.in_(("explicit_body", "official_publication")),
            EventRow.date_conflict.is_(False),
        )

    def _dataset(
        self, rows: list[dict[str, Any]], fields: list[str], **extra: Any
    ) -> dict[str, Any]:
        if len(rows) > 10000 or len(self._datasets) >= 4:
            raise ResearchRejected("RESOURCE_LIMIT")
        dataset = {
            **self._metadata(),
            "dataset_id": str(uuid4()),
            "rows": rows,
            "fields": fields,
            "unit": "events",
            **extra,
        }
        if len(canonical(dataset).encode("utf-8")) > 30000:
            raise ResearchRejected("RESOURCE_LIMIT")
        index = len(self.sources) + 1
        if index > 60:
            raise ResearchRejected("RESOURCE_LIMIT")
        dataset["citation_index"] = index
        self.sources[index] = {
            "index": index,
            "kind": "dataset",
            "title": "数据库统计",
            "source_url": "",
            "dataset": json.loads(canonical(dataset)),
        }
        self._datasets[dataset["dataset_id"]] = json.loads(canonical(dataset))
        return dataset

    async def _aggregate(self, args: dict[str, Any]) -> dict[str, Any]:
        dimension, granularity = args["dimension"], args["granularity"]
        extra: list[Any] = []
        groups: list[Any] = []
        fields = []
        if dimension != "category":
            extra.extend(self._verified_date())
            date_column = (
                func.to_char(EventRow.event_date, "YYYY-MM")
                if granularity == "month"
                else func.to_char(EventRow.event_date, "YYYY-MM-DD")
            )
            groups.append(date_column)
            fields.append("date")
        if dimension != "date":
            groups.append(EventRow.category)
            fields.append("category")
        data = (
            await self.session.execute(
                select(*groups, func.count())
                .where(*self._clauses, *extra)
                .group_by(*groups)
                .order_by(*groups)
                .limit(10001)
            )
        ).all()
        rows = [dict(zip([*fields, "count"], row, strict=True)) for row in data]
        if dimension == "category":
            counts = {row["category"]: row["count"] for row in rows}
            rows = [
                {"category": category.value, "count": counts.get(category.value, 0)}
                for category in Category
            ]
        total = await self._count()
        included = await self._count(*extra)
        return self._dataset(
            rows,
            [*fields, "count"],
            total_events=total,
            included_events=included,
            excluded_unverified_dates=total - included,
            date_basis="verified_day" if extra else "all_scoped_events",
            zero_buckets="omitted" if dimension != "category" else "included",
        )

    async def _compare(self, args: dict[str, Any]) -> dict[str, Any]:
        periods = []
        for name in ("first", "second"):
            start, end = (date.fromisoformat(args[name][key]) for key in ("from", "to"))
            if start > end:
                raise ResearchRejected("INVALID_ARGUMENT")
            if (self.filters.date_from and start < self.filters.date_from) or (
                self.filters.date_to and end > self.filters.date_to
            ):
                raise ResearchRejected("SCOPE_CHANGE_REQUIRED")
            periods.append((start, end))
        rows: list[dict[str, Any]] = []
        for name, (start, end) in zip(("first", "second"), periods, strict=True):
            count = await self._count(
                *self._verified_date(), EventRow.event_date >= start, EventRow.event_date <= end
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
            percentage_change=None if baseline == 0 else (current - baseline) / baseline * 100,
            zero_baseline=baseline == 0,
            unequal_duration=rows[0]["days"] != rows[1]["days"],
            overlapping=max(p[0] for p in periods) <= min(p[1] for p in periods),
            date_basis="verified_day",
            coverage_gaps="not_measured",
        )

    def _chart(self, args: dict[str, Any]) -> dict[str, Any]:
        dataset = self._datasets.get(args["dataset_id"])
        if dataset is None:
            raise ResearchRejected("NOT_FOUND")
        fields = dataset["fields"]
        kind = args["kind"]
        if (kind == "line" and "date" not in fields) or (
            kind == "heatmap" and not {"date", "category"}.issubset(fields)
        ):
            raise ResearchRejected("INVALID_ARGUMENT")
        return {"kind": kind, "dataset": dataset, "values_source": "database_snapshot"}

    async def _evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        event_ids = [UUID(value) for value in args["event_ids"]]
        authorized = set(
            (
                await self.session.scalars(
                    select(EventRow.id).where(*self._clauses, EventRow.id.in_(event_ids))
                )
            ).all()
        )
        if authorized != set(event_ids):
            raise ResearchRejected("NOT_FOUND")
        member = aliased(EventRow)
        rows = list(
            (
                await self.session.scalars(
                    select(EvidenceRow)
                    .join(member, EvidenceRow.event_id == member.id)
                    .where(
                        or_(
                            member.id.in_(authorized),
                            and_(
                                member.status == "merged",
                                member.merged_into_event_id.in_(authorized),
                            ),
                        )
                    )
                    .options(
                        selectinload(EvidenceRow.article_version), selectinload(EvidenceRow.event)
                    )
                    .order_by(EvidenceRow.id)
                    .limit(31)
                )
            ).all()
        )
        if len(rows) > 30:
            raise ResearchRejected("RESOURCE_LIMIT")
        output: list[dict[str, Any]] = []
        for row in rows:
            paragraph = row.article_version.paragraphs.get(row.paragraph_id)
            if not row.quote_text or not paragraph or row.quote_text not in paragraph:
                raise ResearchRejected("TOOL_UNAVAILABLE")
            quote_hash = hashlib.sha256(row.quote_text.encode()).hexdigest()
            if row.quote_hash and row.quote_hash != quote_hash:
                raise ResearchRejected("TOOL_UNAVAILABLE")
            evidence = Evidence.model_validate(
                {
                    "id": row.id,
                    "event_id": row.event_id,
                    "article_version_id": row.article_version_id,
                    "paragraph_id": row.paragraph_id,
                    "quote_text": row.quote_text,
                    "source_url": row.article_version.source_url,
                    "title": row.article_version.title,
                    "verification_status": row.verification_status,
                    "source_published_at": row.article_version.published_at,
                    "event_date": row.event.event_date,
                    "canonical_event_id": row.event.merged_into_event_id or row.event_id,
                    "claim_key": row.claim_key,
                    "claim_text": row.claim_text,
                    "quote_hash": quote_hash,
                    "support_type": row.support_type,
                }
            )
            citation_id = str(row.id)
            index = next(
                (
                    i
                    for i, source in self.sources.items()
                    if source.get("evidence_id") == citation_id
                ),
                0,
            )
            if not index:
                index = len(self.sources) + 1 + sum(1 for item in output if item.get("_new_index"))
            output.append(
                {
                    "citation_id": citation_id,
                    "citation_index": index,
                    "_new_index": index not in self.sources,
                    **evidence.model_dump(mode="json"),
                }
            )
        result = {**self._metadata(), "evidence": output, "complete": True}
        if len(canonical(result).encode("utf-8")) > 32768:
            raise ResearchRejected("RESOURCE_LIMIT")
        if any(item["citation_index"] > 60 for item in output):
            raise ResearchRejected("RESOURCE_LIMIT")
        for item in output:
            item.pop("_new_index")
            self.citations[item["citation_id"]] = Evidence.model_validate(item)
            self.retrieved_events.add(str(item["canonical_event_id"]))
            index = item["citation_index"]
            self.sources[index] = {
                "index": index,
                "kind": "evidence",
                "evidence_id": item["citation_id"],
                "event_id": item["canonical_event_id"],
                **{
                    key: item[key]
                    for key in (
                        "article_version_id",
                        "paragraph_id",
                        "quote_text",
                        "source_url",
                        "title",
                        "verification_status",
                        "support_type",
                    )
                },
            }
        return result
