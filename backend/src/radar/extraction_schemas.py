from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .date_literals import explicit_dates

Category = Literal[
    "model_release", "agent_tool", "framework_sdk", "research", "product", "industry"
]
EntityType = Literal["company", "person", "product", "model", "organization", "technology"]
EntityRole = Literal["subject", "product", "mention"]


class ExtractedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraph_id: str = Field(min_length=1, max_length=100)
    quote_text: str = Field(min_length=1)
    claim_key: str | None = Field(default=None, max_length=100)
    claim_text: str | None = None
    support_type: Literal["direct", "context", "contradicts"] = "direct"


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_name: str = Field(min_length=1, max_length=200)
    entity_type: EntityType
    role: EntityRole


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relevant: bool
    title_zh: str = Field(default="", max_length=500)
    summary_zh: str = Field(default="", max_length=3000)
    category: Category | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    event_date: date | None = None
    date_precision: Literal["day", "month", "unknown"] = "unknown"
    date_basis: Literal["explicit_body", "official_publication", "unknown"] = "unknown"
    date_evidence_paragraph_id: str | None = Field(default=None, max_length=100)
    entities: list[ExtractedEntity] = Field(default_factory=list, max_length=30)
    evidence: list[ExtractedEvidence] = Field(default_factory=list, max_length=20)

    def validate_publishable(self, paragraphs: dict[str, str]) -> None:
        if not self.relevant:
            return
        if (
            not self.title_zh.strip()
            or not self.summary_zh.strip()
            or self.category is None
            or self.importance is None
        ):
            raise ValueError("relevant extraction lacks required event fields")
        if not any("\u3400" <= char <= "\u9fff" for char in self.title_zh):
            raise ValueError("title_zh must contain Chinese text")
        if not any("\u3400" <= char <= "\u9fff" for char in self.summary_zh):
            raise ValueError("summary_zh must contain Chinese text")
        if not self.entities:
            raise ValueError("relevant extraction requires entities")
        if any(not item.canonical_name.strip() for item in self.entities):
            raise ValueError("entity names must not be blank")
        if not self.evidence:
            raise ValueError("relevant extraction requires evidence")
        if self.date_precision == "unknown":
            if (
                self.event_date is not None
                or self.date_evidence_paragraph_id is not None
                or self.date_basis != "unknown"
            ):
                raise ValueError("unknown event date must not carry a date or date evidence")
        elif (
            self.event_date is None
            or self.date_evidence_paragraph_id is None
            or self.date_basis == "unknown"
        ):
            raise ValueError("known event date requires explicit paragraph evidence")
        for item in self.evidence:
            paragraph = paragraphs.get(item.paragraph_id)
            if not item.quote_text.strip() or paragraph is None or item.quote_text not in paragraph:
                raise ValueError("evidence quote is not an exact paragraph substring")
        if self.date_evidence_paragraph_id is not None and not any(
            item.paragraph_id == self.date_evidence_paragraph_id
            and self.event_date is not None
            and self.event_date in explicit_dates(item.quote_text, self.date_precision)
            for item in self.evidence
        ):
            raise ValueError("date evidence quote must contain the extracted date")
