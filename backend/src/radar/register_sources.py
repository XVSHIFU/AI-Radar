import argparse
import asyncio
import json
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import Executable

from .config import get_settings
from .models import SourceRow


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    feed_url: str


RELEASE_SOURCES = (
    SourceDefinition("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    SourceDefinition("Google Research", "https://research.google/blog/rss/"),
    SourceDefinition("AWS Machine Learning", "https://aws.amazon.com/blogs/machine-learning/feed/"),
)


CURATED_SOURCE_CANDIDATES = (
    SourceDefinition("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    SourceDefinition("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
    SourceDefinition("Google Research", "https://research.google/blog/rss/"),
    SourceDefinition("AWS Machine Learning", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    SourceDefinition("NVIDIA Technical Blog", "https://developer.nvidia.com/blog/feed/"),
)


def source_upserts(enabled: bool) -> list[Executable]:
    statements: list[Executable] = []
    for source in CURATED_SOURCE_CANDIDATES:
        host = urlsplit(source.feed_url).hostname
        assert host is not None
        statements.append(
            insert(SourceRow)
            .values(
                id=uuid5(NAMESPACE_URL, source.feed_url),
                name=source.name,
                feed_url=source.feed_url,
                enabled=enabled,
                health="unverified",
                consecutive_failures=0,
                canonical_host=host,
                channel_type="rss",
            )
            .on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "feed_url": source.feed_url,
                    "enabled": enabled,
                    "canonical_host": host,
                    "channel_type": "rss",
                },
            )
        )
    return statements


async def register_sources(sessions: async_sessionmaker[AsyncSession], *, enabled: bool) -> int:
    async with sessions() as session, session.begin():
        for statement in source_upserts(enabled):
            await session.execute(statement)
    return len(CURATED_SOURCE_CANDIDATES)


async def register_release_sources(sessions: async_sessionmaker[AsyncSession]) -> int:
    """Seed only an empty installation; never reset an operator's source choices."""
    async with sessions() as session, session.begin():
        existing = await session.scalar(select(func.count()).select_from(SourceRow))
        if existing:
            return 0
        for source in RELEASE_SOURCES:
            host = urlsplit(source.feed_url).hostname
            assert host is not None
            session.add(
                SourceRow(
                    id=uuid5(NAMESPACE_URL, source.feed_url),
                    name=source.name,
                    feed_url=source.feed_url,
                    enabled=True,
                    health="unverified",
                    consecutive_failures=0,
                    canonical_host=host,
                    channel_type="rss",
                )
            )
    return len(RELEASE_SOURCES)


async def run(enabled: bool, release_defaults: bool = False) -> None:
    settings = get_settings()
    url = settings.sqlalchemy_url()
    if settings.radar_data_mode != "postgres" or url is None:
        raise RuntimeError("source registration requires configured PostgreSQL mode")
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        count = await (
            register_release_sources(sessions)
            if release_defaults
            else register_sources(sessions, enabled=enabled)
        )
    finally:
        await engine.dispose()
    print(
        json.dumps(
            {
                "registered": count,
                "enabled": True if release_defaults else enabled,
                "health": "unverified",
                "production_body_validation": "required",
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Idempotently register the five curated RSS source candidates."
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Explicitly enable sources; default registration is disabled and unverified.",
    )
    parser.add_argument(
        "--release-defaults",
        action="store_true",
        help="Seed three enabled feeds only on an empty installation.",
    )
    args = parser.parse_args()
    asyncio.run(run(enabled=args.enable, release_defaults=args.release_defaults))


if __name__ == "__main__":
    main()
