from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class Category(StrEnum):
    MODEL_RELEASE = "model_release"
    AGENT_TOOL = "agent_tool"
    FRAMEWORK_SDK = "framework_sdk"
    RESEARCH = "research"
    PRODUCT = "product"
    INDUSTRY = "industry"


class Event(BaseModel):
    id: UUID
    title_zh: str
    summary_zh: str
    category: Category
    importance: int = Field(ge=1, le=5)
    event_date: date | None
    date_precision: Literal["day", "month", "unknown"]
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    entities: list[str]
    content_version: int = Field(ge=1)
    date_basis: Literal[
        "explicit_body",
        "official_publication",
        "report_date_unverified",
        "unknown",
    ] = "unknown"
    canonical_id: UUID | None = None
    merged_source_event_ids: list[UUID] = Field(default_factory=list)
    date_conflict: bool = False


class Filters(BaseModel):
    q: str | None = None
    category: Category | None = None
    date_from: date | None = None
    date_to: date | None = None
    min_importance: int | None = Field(default=None, ge=1, le=5)
    entity_ids: list[UUID] = Field(default_factory=list)
    entity_match: Literal["all", "any"] = "all"
    event_ids: list[UUID] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        self.entity_ids = list(dict.fromkeys(self.entity_ids))
        return self

    @field_validator("entity_ids", "event_ids")
    @classmethod
    def deduplicate_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class EventPage(BaseModel):
    items: list[Event]
    total: int
    total_relation: Literal["eq"] = "eq"
    next_cursor: str | None
    filters_applied: Filters
    as_of: datetime
    data_revision: str
    request_id: str
    data_mode: Literal["fixture", "postgres"]


class SearchResponse(BaseModel):
    items: list[Event]
    scope_total: int = Field(ge=0)
    retrieved_count: int = Field(ge=0)
    keyword_count: int = Field(ge=0)
    semantic_count: int = Field(ge=0)
    retrieval_mode: Literal["keyword", "hybrid"]
    degraded_reason: str | None
    embedding_profile: str | None
    filters_applied: Filters
    as_of: datetime
    data_revision: str
    request_id: str
    data_mode: Literal["postgres"] = "postgres"


class DailyInsight(BaseModel):
    date: date
    count: int = Field(ge=0)


class CategoryInsight(BaseModel):
    category: Category
    count: int = Field(ge=0)


class DailyCategoryInsight(BaseModel):
    date: date
    category: Category
    count: int = Field(ge=0)


class InsightsResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    total_events: int = Field(ge=0)
    total_relation: Literal["eq"] = "eq"
    daily: list[DailyInsight]
    categories: list[CategoryInsight]
    daily_categories: list[DailyCategoryInsight]
    as_of: datetime
    data_revision: str
    data_mode: Literal["fixture", "postgres"]
    request_id: str


class Evidence(BaseModel):
    id: UUID
    event_id: UUID
    article_version_id: UUID
    paragraph_id: str
    quote_text: str
    source_url: HttpUrl
    title: str
    verification_status: Literal["synthetic_verified", "unverified"]
    source_published_at: datetime | None
    event_date: date | None
    canonical_event_id: UUID | None = None
    claim_key: str | None = None
    claim_text: str | None = None
    quote_hash: str | None = None
    support_type: Literal["direct", "context", "contradicts"] = "direct"


class EvidencePage(BaseModel):
    items: list[Evidence]
    data_mode: Literal["fixture", "postgres"]


class Article(BaseModel):
    id: UUID
    title: str
    source_url: HttpUrl
    paragraphs: dict[str, str]
    synthetic: bool


class EventDetail(Event):
    evidence: list[Evidence]
    articles: list[Article]
    data_mode: Literal["fixture", "postgres"]


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    filters: Filters | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    filters: Filters = Field(default_factory=Filters)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=6)
    event_ids: list[UUID] = Field(default_factory=list, max_length=3)
    timezone: str = "Asia/Shanghai"
    answer_mode: str = "concise"
    client_request_id: str

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if sum(len(item.content) for item in self.history) > 12000:
            raise ValueError("history content must not exceed 12000 characters")
        self.event_ids = list(dict.fromkeys(self.event_ids))
        nested_event_ids = self.filters.event_ids
        if nested_event_ids and self.event_ids and nested_event_ids != self.event_ids:
            raise ValueError("event_ids must match filters.event_ids when both are provided")
        if nested_event_ids:
            self.event_ids = nested_event_ids
        elif self.event_ids:
            self.filters.event_ids = list(self.event_ids)
        return self


class ClarificationCandidate(BaseModel):
    label: str
    entity_id: UUID | None


class EventTarget(BaseModel):
    event_id: UUID
    title_zh: str | None
    status: Literal["matched", "filtered_out", "not_found"]


class QueryPlan(BaseModel):
    intent: Literal[
        "structured_list", "structured_summary", "entity_lookup", "semantic_search", "follow_up"
    ]
    filters: Filters
    timezone: str
    business_date: date
    date_until_exclusive: date | None
    constraints_origin: dict[str, str]
    free_text: str
    requires_clarification: bool
    clarification_candidates: list[ClarificationCandidate]
    warnings: list[str]
    history_turns_considered: int = Field(default=0, ge=0, le=6)
    history_user_turns_used: int = Field(default=0, ge=0, le=1)
    event_targets: list[EventTarget] = Field(default_factory=list)
    entity_roles: list[Literal["subject", "product"]] = ["subject", "product"]
    data_mode: Literal["fixture", "postgres"] | None = None
    request_id: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    request_id: str
    details: dict[str, Any] | None = None


class IngestRunRequest(BaseModel):
    source_ids: list[UUID] = Field(min_length=1)

    @model_validator(mode="after")
    def deduplicate_sources(self) -> Self:
        self.source_ids = list(dict.fromkeys(self.source_ids))
        return self


class IngestRun(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    discovered_urls: int
    fetched_articles: int
    new_articles: int
    updated_articles: int
    event_candidates: int
    found: int = 0
    kept: int = 0
    candidates: int = 0
    versions: int = 0
    parser_failures: int
    failed_jobs: int
    cost: Decimal | None
    cost_status: Literal["actual", "estimated", "unknown"]
    error_summary: str | None


class IngestRunCreated(BaseModel):
    run_id: UUID
    status: str
    idempotent_replay: bool
