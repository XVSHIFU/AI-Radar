from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "model_release", "agent_tool", "framework_sdk", "research", "product", "industry"
]
EntityType = Literal["company", "person", "product", "model", "organization", "technology"]
EntityRole = Literal["subject", "product", "mention"]


class ExtractedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraph_id: str = Field(min_length=1, max_length=100)
    quote_text: str = Field(min_length=1)


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
        for item in self.evidence:
            paragraph = paragraphs.get(item.paragraph_id)
            if not item.quote_text.strip() or paragraph is None or item.quote_text not in paragraph:
                raise ValueError("evidence quote is not an exact paragraph substring")
