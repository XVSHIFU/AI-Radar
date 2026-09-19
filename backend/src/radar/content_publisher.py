from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from .event_merge_service import canonical_counts
from .event_write_lock import lock_event_writes
from .extraction_schemas import ExtractionResult
from .models import (
    ArticleCandidateRow,
    ArticleVersionRow,
    EntityAliasRow,
    EntityRow,
    EventArticleRow,
    EventEntityRow,
    EventRow,
    EvidenceRow,
)
from .normalize import normalize_text
from .retrieval import SEARCH_CONFIG_VERSION, search_document


async def mark_candidates(session: AsyncSession, version_id: UUID, status: str) -> None:
    await session.execute(
        update(ArticleCandidateRow)
        .where(
            ArticleCandidateRow.article_version_id == version_id,
            ArticleCandidateRow.status.in_(
                ("needs_review", "extraction_failed", "extraction_unknown", "filtered")
            ),
        )
        .values(status=status)
    )


async def publish_extraction(
    session: AsyncSession,
    version: ArticleVersionRow,
    extraction: ExtractionResult,
    *,
    alias_source: str = "llm",
) -> UUID | None:
    """Validate and publish inside the caller's transaction; None means superseded."""
    extraction.validate_publishable(version.paragraphs)
    await lock_event_writes(session)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:article_id, 0))"),
        {"article_id": str(version.article_id)},
    )
    latest_version_id = await session.scalar(
        select(ArticleVersionRow.id)
        .where(ArticleVersionRow.article_id == version.article_id)
        .order_by(ArticleVersionRow.fetched_at.desc(), ArticleVersionRow.id.desc())
        .limit(1)
    )
    if latest_version_id != version.id:
        await mark_candidates(session, version.id, "superseded")
        return None
    source_count = int(
        (
            await session.scalar(
                select(func.count(func.distinct(ArticleCandidateRow.source_id)))
                .join(
                    ArticleVersionRow,
                    ArticleVersionRow.id == ArticleCandidateRow.article_version_id,
                )
                .where(ArticleVersionRow.article_id == version.article_id)
            )
        )
        or 0
    )
    event = await session.scalar(
        select(EventRow)
        .join(EventArticleRow, EventArticleRow.event_id == EventRow.id)
        .where(EventArticleRow.article_id == version.article_id)
        .with_for_update()
    )
    if event is not None:
        prior_evidence = await session.scalar(
            select(EvidenceRow.id)
            .where(
                EvidenceRow.event_id == event.id,
                EvidenceRow.article_version_id == version.id,
            )
            .limit(1)
        )
        if prior_evidence is not None:
            await mark_candidates(session, version.id, "published")
            return event.id
    if event is None:
        event = EventRow(
            id=uuid4(),
            title_zh=extraction.title_zh.strip(),
            summary_zh=extraction.summary_zh.strip(),
            category=str(extraction.category),
            importance=int(extraction.importance or 1),
            event_date=extraction.event_date,
            date_precision=extraction.date_precision,
            date_basis=extraction.date_basis,
            status="published",
            source_count=source_count,
            evidence_count=len(extraction.evidence),
            content_version=1,
            search_document=search_document(
                extraction.title_zh.strip(), extraction.summary_zh.strip()
            ),
            search_config_version=SEARCH_CONFIG_VERSION,
            search_indexed_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()
        session.add(
            EventArticleRow(
                event_id=event.id,
                article_id=version.article_id,
                relation_type="supports",
                is_primary=True,
            )
        )
    else:
        event.title_zh = extraction.title_zh.strip()
        event.summary_zh = extraction.summary_zh.strip()
        event.category = str(extraction.category)
        event.importance = int(extraction.importance or 1)
        if extraction.event_date is not None:
            if (
                event.date_basis in {"explicit_body", "official_publication"}
                and event.event_date != extraction.event_date
            ):
                event.date_conflict = True
            else:
                event.event_date = extraction.event_date
                event.date_precision = extraction.date_precision
                event.date_basis = extraction.date_basis
        if event.status != "merged":
            event.status = "published"
        event.source_count = source_count
        event.content_version += 1
        event.evidence_count += len(extraction.evidence)
        event.search_document = search_document(event.title_zh, event.summary_zh)
        event.search_config_version = SEARCH_CONFIG_VERSION
        event.search_indexed_at = datetime.now(UTC)
        event.updated_at = datetime.now(UTC)
        await session.execute(
            text(
                "UPDATE event_embeddings_v1 SET status='stale', embedding=NULL, "
                "indexed_at=NULL WHERE event_id=:event_id"
            ),
            {"event_id": event.id},
        )
    date_evidence_id = None
    for evidence_item in extraction.evidence:
        evidence_row = EvidenceRow(
            id=uuid4(),
            event_id=event.id,
            article_version_id=version.id,
            paragraph_id=evidence_item.paragraph_id,
            quote_text=evidence_item.quote_text,
            claim_key=evidence_item.claim_key,
            claim_text=evidence_item.claim_text,
            quote_hash=hashlib.sha256(evidence_item.quote_text.encode()).hexdigest(),
            support_type=evidence_item.support_type,
            verification_status="unverified",
        )
        session.add(evidence_row)
        if evidence_item.paragraph_id == extraction.date_evidence_paragraph_id:
            date_evidence_id = evidence_row.id
    await session.flush()
    if date_evidence_id is not None and not event.date_conflict:
        event.date_evidence_id = date_evidence_id
    if event.merged_into_event_id is not None:
        canonical = await session.get(EventRow, event.merged_into_event_id, with_for_update=True)
        if canonical is not None:
            canonical.source_count, canonical.evidence_count = await canonical_counts(
                session, canonical.id
            )
            canonical.content_version += 1
            canonical.updated_at = datetime.now(UTC)
    for entity_item in extraction.entities:
        entity_name = entity_item.canonical_name.strip()
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:entity_name, 0))"),
            {"entity_name": entity_name},
        )
        entity = await session.scalar(
            select(EntityRow).where(EntityRow.canonical_name == entity_name)
        )
        if entity is None:
            entity = EntityRow(
                id=uuid4(),
                canonical_name=entity_name,
                entity_type=entity_item.entity_type,
            )
            session.add(entity)
            await session.flush()
            session.add(
                EntityAliasRow(
                    id=uuid4(),
                    entity_id=entity.id,
                    normalized_alias=normalize_text(entity.canonical_name),
                    alias_source=alias_source,
                )
            )
        relation = await session.get(EventEntityRow, (event.id, entity.id))
        if relation is None:
            session.add(
                EventEntityRow(event_id=event.id, entity_id=entity.id, role=entity_item.role)
            )
    await mark_candidates(session, version.id, "published")
    return event.id
