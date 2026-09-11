from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .schemas import Article, Event, Evidence, Filters


@dataclass(frozen=True)
class Page:
    items: list[Event]
    total: int
    next_cursor: str | None
    as_of: datetime
    data_revision: str


class EventRepository(Protocol):
    async def list_events(self, filters: Filters, limit: int, cursor: str | None) -> Page: ...

    async def evidence_for(self, event_id: UUID) -> list[Evidence]: ...

    async def event(self, event_id: UUID) -> Event | None: ...

    async def articles_for(self, event_id: UUID) -> list[Article]: ...

    async def ready(self) -> bool: ...

    async def stats(self) -> dict[str, object]: ...

    async def insights(self) -> dict[str, object]: ...

    async def sources(self) -> list[dict[str, object]]: ...


class RepositoryUnavailable(RuntimeError):
    pass


class InvalidCursor(ValueError):
    pass
