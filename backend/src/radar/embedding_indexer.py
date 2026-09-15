from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .event_write_lock import lock_event_writes
from .local_bge import LocalBgeM3Provider
from .models import EmbeddingProfileRow, EventRow
from .retrieval import EmbeddingProvider, checked_query_embedding


@dataclass(frozen=True)
class IndexResult:
    profile_id: str
    indexed: int
    skipped: int
    activated: bool


class EmbeddingIndexer:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], provider: EmbeddingProvider
    ) -> None:
        self.sessions = sessions
        self.provider = provider

    async def _profile(self) -> UUID:
        profile = self.provider.profile
        async with self.sessions() as session, session.begin():
            await session.execute(
                insert(EmbeddingProfileRow)
                .values(
                    id=uuid4(),
                    provider=profile.provider,
                    model_id=profile.model_id,
                    revision=profile.revision,
                    dimension=profile.dimension,
                    normalize=profile.normalize,
                    input_template_version=profile.input_template_version,
                    active=False,
                    status="indexing",
                )
                .on_conflict_do_nothing(constraint="uq_embedding_profile_identity")
            )
            row = (
                await session.execute(
                    select(EmbeddingProfileRow.id, EmbeddingProfileRow.dimension).where(
                        EmbeddingProfileRow.provider == profile.provider,
                        EmbeddingProfileRow.model_id == profile.model_id,
                        EmbeddingProfileRow.revision == profile.revision,
                        EmbeddingProfileRow.normalize == profile.normalize,
                        EmbeddingProfileRow.input_template_version
                        == profile.input_template_version,
                    )
                )
            ).one()
            if row.dimension != profile.dimension:
                raise ValueError("registered embedding profile dimension mismatch")
            return UUID(str(row.id))

    async def run(self, *, limit: int = 100, activate: bool = False) -> IndexResult:
        if not 1 <= limit <= 5000:
            raise ValueError("index batch limit must be between 1 and 5000")
        await checked_query_embedding(self.provider, "dimension probe")
        profile_id = await self._profile()
        async with self.sessions() as session:
            events = list(
                (
                    await session.scalars(
                        select(EventRow)
                        .where(
                            EventRow.status == "published",
                            text(
                                "NOT EXISTS (SELECT 1 FROM event_embeddings_v1 ee "
                                "WHERE ee.event_id=events.id AND ee.profile_id=:profile_id "
                                "AND ee.status='ready' AND "
                                "ee.event_content_version=events.content_version "
                                "AND ee.input_hash=encode(sha256(convert_to(events.title_zh "
                                "|| chr(10) "
                                "|| events.summary_zh, 'UTF8')), 'hex'))"
                            ),
                        )
                        .params(profile_id=profile_id)
                        .order_by(EventRow.updated_at, EventRow.id)
                        .limit(limit)
                    )
                ).all()
            )
        indexed = 0
        skipped = 0
        for event in events:
            input_text = f"{event.title_zh}\n{event.summary_zh}"
            input_hash = hashlib.sha256(input_text.encode()).hexdigest()
            async with self.sessions() as session:
                current = await session.scalar(
                    text(
                        "SELECT 1 FROM event_embeddings_v1 WHERE event_id=:event_id "
                        "AND profile_id=:profile_id AND status='ready' "
                        "AND input_hash=:input_hash AND event_content_version=:content_version"
                    ),
                    {
                        "event_id": event.id,
                        "profile_id": profile_id,
                        "input_hash": input_hash,
                        "content_version": event.content_version,
                    },
                )
            if current:
                skipped += 1
                continue
            vector = await checked_query_embedding(self.provider, input_text)
            rendered = "[" + ",".join(str(value) for value in vector) + "]"
            async with self.sessions() as session, session.begin():
                await lock_event_writes(session)
                current_event = await session.get(EventRow, event.id, with_for_update=True)
                if (
                    current_event is None
                    or current_event.status != "published"
                    or (
                        current_event.content_version != event.content_version
                        or hashlib.sha256(
                            f"{current_event.title_zh}\n{current_event.summary_zh}".encode()
                        ).hexdigest()
                        != input_hash
                    )
                ):
                    skipped += 1
                    continue
                await session.execute(
                    text(
                        "INSERT INTO event_embeddings_v1 "
                        "(event_id,profile_id,input_hash,event_content_version,"
                        "embedding,status,indexed_at) "
                        "VALUES (:event_id,:profile_id,:input_hash,:content_version,"
                        "CAST(:embedding AS vector),'ready',now()) "
                        "ON CONFLICT (event_id,profile_id) DO UPDATE SET "
                        "input_hash=excluded.input_hash,event_content_version=excluded.event_c"
                        "ontent_version,"
                        "embedding=excluded.embedding,status='ready',indexed_at=excluded.indexed_at"
                    ),
                    {
                        "event_id": event.id,
                        "profile_id": profile_id,
                        "input_hash": input_hash,
                        "content_version": event.content_version,
                        "embedding": rendered,
                    },
                )
            indexed += 1
        activated = False
        if activate:
            async with self.sessions() as session, session.begin():
                await lock_event_writes(session)
                missing = int(
                    (
                        await session.scalar(
                            text(
                                "SELECT count(*) FROM events e WHERE e.status='published' "
                                "AND NOT EXISTS "
                                "(SELECT 1 FROM event_embeddings_v1 ee WHERE ee.event_id=e.id "
                                "AND ee.profile_id=:profile_id AND ee.status='ready' "
                                "AND ee.event_content_version=e.content_version "
                                "AND ee.input_hash=encode(sha256(convert_to(e.title_zh || "
                                "chr(10) || "
                                "e.summary_zh, 'UTF8')), 'hex'))"
                            ),
                            {"profile_id": profile_id},
                        )
                    )
                    or 0
                )
                if missing:
                    raise RuntimeError(
                        f"cannot activate profile with {missing} stale or missing events"
                    )
                await session.execute(update(EmbeddingProfileRow).values(active=False))
                await session.execute(
                    update(EmbeddingProfileRow)
                    .where(EmbeddingProfileRow.id == profile_id)
                    .values(active=True, status="ready")
                )
                activated = True
        return IndexResult(str(profile_id), indexed, skipped, activated)


async def _main(limit: int, activate: bool) -> None:
    settings = get_settings()
    url = settings.sqlalchemy_url()
    if url is None or settings.embedding_model_dir is None or not settings.embedding_model_revision:
        raise SystemExit("database and pinned embedding model settings are required")
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        provider = LocalBgeM3Provider(
            settings.embedding_model_dir,
            settings.embedding_model_revision,
            threads=settings.embedding_threads,
        )
        result = await EmbeddingIndexer(
            async_sessionmaker(engine, expire_on_commit=False), provider
        ).run(limit=limit, activate=activate)
        print(json.dumps(result.__dict__, sort_keys=True))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.limit, args.activate))
