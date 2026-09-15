import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from .cursor import decode_cursor, encode_cursor
from .normalize import normalize_text
from .queryplanner import EntityResolution, ResolvedEntity, resolve_confirmed_entities
from .repository import InsightsSnapshot, InvalidCursor, Page
from .schemas import Article, Event, Evidence, Filters

DEEPSEEK_ID = UUID("10000000-0000-4000-8000-000000000001")
TEAM_ID = UUID("10000000-0000-4000-8000-000000000002")
ALIASES = {"deepseek": {DEEPSEEK_ID}, "深度求索": {DEEPSEEK_ID}, "示例研究团队": {TEAM_ID}}
ENTITY_IDS = {"DeepSeek": DEEPSEEK_ID, "示例研究团队": TEAM_ID}
EVIDENCE_EVENT_ID = UUID("00000000-0000-4000-8000-000000000002")
ARTICLE_VERSION_ID = UUID("30000000-0000-4000-8000-000000000001")
FROZEN_PARAGRAPHS = {
    "synthetic-v1-p1": "合成段落：DeepSeek 示例研究模型预览用于验证段落级证据定位。"
}


class FixtureRepository:
    def __init__(
        self,
        fixture_path: Path,
        cursor_secret: str,
        items: list[dict[str, Any]] | None = None,
    ):
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.dataset = str(payload["dataset"])
        source_items = items if items is not None else payload["items"]
        self.events = [
            event.model_copy(
                update={
                    "source_count": 1 if event.id == EVIDENCE_EVENT_ID else 0,
                    "evidence_count": 1 if event.id == EVIDENCE_EVENT_ID else 0,
                }
            )
            for event in (
                Event.model_validate(
                    {"date_basis": "explicit_body" if item.get("event_date") else "unknown", **item}
                )
                for item in source_items
            )
        ]
        self.cursor_secret = cursor_secret
        self.now = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)

    def _actual_entity_ids(self, event: Event) -> set[UUID]:
        return {ENTITY_IDS[name] for name in event.entities if name in ENTITY_IDS}

    async def resolve_entities(self, text: str) -> EntityResolution:
        normalized = normalize_text(text)
        labels = {DEEPSEEK_ID: "DeepSeek", TEAM_ID: "示例研究团队"}
        alias_candidates = {
            alias: [ResolvedEntity(labels[item], item) for item in entity_ids]
            for alias, entity_ids in ALIASES.items()
        }
        return resolve_confirmed_entities(normalized, alias_candidates)

    def _matching_events(self, filters: Filters) -> list[Event]:
        events = list({event.id: event for event in self.events}.values())
        if filters.event_ids:
            event_ids = set(filters.event_ids)
            events = [event for event in events if event.id in event_ids]
        if filters.category:
            events = [event for event in events if event.category == filters.category]
        if filters.date_from or filters.date_to:
            events = [
                event
                for event in events
                if event.date_basis in ("explicit_body", "official_publication")
                and not event.date_conflict
            ]
        if filters.date_from:
            events = [
                event
                for event in events
                if event.date_precision == "day"
                and event.event_date
                and event.event_date >= filters.date_from
            ]
        if filters.date_to:
            events = [
                event
                for event in events
                if event.date_precision == "day"
                and event.event_date
                and event.event_date <= filters.date_to
            ]
        if filters.min_importance:
            events = [event for event in events if event.importance >= filters.min_importance]
        required_ids = set(filters.entity_ids)
        if required_ids:
            events = [
                event
                for event in events
                if (
                    required_ids <= self._actual_entity_ids(event)
                    if filters.entity_match == "all"
                    else bool(required_ids & self._actual_entity_ids(event))
                )
            ]
        if filters.q:
            query = normalize_text(filters.q)
            alias_ids = ALIASES.get(query)
            if alias_ids:
                events = [
                    event for event in events if bool(alias_ids & self._actual_entity_ids(event))
                ]
            else:
                events = [
                    event
                    for event in events
                    if query
                    in normalize_text(" ".join((event.title_zh, event.summary_zh, *event.entities)))
                ]
        return events

    async def list_events(self, filters: Filters, limit: int, cursor: str | None) -> Page:
        events = self._matching_events(filters)
        events.sort(
            key=lambda event: (
                event.event_date is not None,
                event.event_date,
                event.id,
            ),
            reverse=True,
        )
        total = len(events)
        if cursor:
            last_date, last_id = decode_cursor(cursor, filters, self.cursor_secret)
            position = next(
                (
                    index
                    for index, event in enumerate(events)
                    if event.event_date == last_date and event.id == last_id
                ),
                None,
            )
            if position is None:
                raise InvalidCursor("cursor position is no longer available")
            events = events[position + 1 :]
        items = events[:limit]
        next_cursor = None
        if len(events) > limit:
            last = items[-1]
            next_cursor = encode_cursor(last.event_date, last.id, filters, self.cursor_secret)
        return Page(
            items,
            total,
            next_cursor,
            self.now,
            f"{self.dataset}-no-cross-page-snapshot",
        )

    async def event(self, event_id: UUID) -> Event | None:
        return next((event for event in self.events if event.id == event_id), None)

    async def evidence_for(self, event_id: UUID) -> list[Evidence]:
        if event_id != EVIDENCE_EVENT_ID:
            return []
        return [
            Evidence(
                id=UUID("20000000-0000-4000-8000-000000000001"),
                event_id=event_id,
                article_version_id=ARTICLE_VERSION_ID,
                paragraph_id="synthetic-v1-p1",
                quote_text=FROZEN_PARAGRAPHS["synthetic-v1-p1"],
                source_url="https://example.invalid/synthetic/deepseek-preview",
                title="合成来源版本 v1（非真实报道）",
                verification_status="synthetic_verified",
                source_published_at=self.now,
                event_date=next(event.event_date for event in self.events if event.id == event_id),
            )
        ]

    async def articles_for(self, event_id: UUID) -> list[Article]:
        if event_id != EVIDENCE_EVENT_ID:
            return []
        return [
            Article(
                id=ARTICLE_VERSION_ID,
                title="合成来源版本 v1（非真实报道）",
                source_url="https://example.invalid/synthetic/deepseek-preview",
                paragraphs=dict(FROZEN_PARAGRAPHS),
                synthetic=True,
            )
        ]

    async def stats(self) -> dict[str, object]:
        return {
            "total_events": len(self.events),
            "total_sources": 1,
            "categories": dict(Counter(item.category.value for item in self.events)),
            "scope": "global",
            "as_of": self.now,
            "data_revision": self.dataset,
        }

    async def insights(self) -> dict[str, object]:
        today = self.now.date()
        headlines = sorted(
            [event for event in self.events if event.event_date == today],
            key=lambda event: (event.importance, event.id),
            reverse=True,
        )[:3]
        tags = [
            {"name": name, "count": count}
            for name, count in Counter(
                name for item in self.events for name in item.entities
            ).most_common(8)
        ]
        return {
            "headlines": headlines,
            "tags": tags,
            "scope": "global",
            "as_of": self.now,
            "data_revision": self.dataset,
        }

    async def insight_summary(self, filters: Filters) -> InsightsSnapshot:
        events = self._matching_events(filters)
        return InsightsSnapshot(
            total_events=len(events),
            daily=dict(
                Counter(event.event_date for event in events if event.event_date is not None)
            ),
            categories=dict(Counter(event.category for event in events)),
            daily_categories=dict(
                Counter(
                    (event.event_date, event.category)
                    for event in events
                    if event.event_date is not None
                )
            ),
            as_of=self.now,
            data_revision=self.dataset,
        )

    async def sources(self) -> list[dict[str, object]]:
        return [
            {
                "id": "40000000-0000-4000-8000-000000000001",
                "name": "合成来源（非真实采集）",
                "feed_url": "https://example.invalid/synthetic/feed",
                "enabled": False,
                "health": "synthetic",
                "last_success_at": None,
                "consecutive_failures": 0,
            }
        ]

    async def ready(self) -> bool:
        return False
