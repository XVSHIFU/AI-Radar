"""Preview classification of uncategorized articles; --apply writes only empty categories."""

import argparse
import asyncio
import json
from collections import Counter
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .article_rules import classify_article
from .config import get_settings
from .models import ArticleRow, SourceRow


async def run(apply: bool = False) -> dict[str, object]:
    url = get_settings().sqlalchemy_url()
    if url is None:
        raise RuntimeError("PostgreSQL configuration required")
    engine = create_async_engine(url)
    counts: Counter[str] = Counter()
    changed = 0
    try:
        async with async_sessionmaker(engine)() as session, session.begin():
            rows = (
                await session.execute(
                    select(ArticleRow.id, ArticleRow.title, ArticleRow.excerpt, SourceRow.feed_url)
                    .join(SourceRow, SourceRow.id == ArticleRow.source_id)
                    .where(ArticleRow.category.is_(None), ArticleRow.status == "published")
                )
            ).all()
            for row in rows:
                category = classify_article(
                    row.title or "", summary=row.excerpt, source_url=row.feed_url
                )
                counts[category or "unclassified"] += 1
                if apply and category:
                    # A concurrent administrator edit must win over this backfill.
                    result = await session.execute(
                        update(ArticleRow)
                        .where(ArticleRow.id == row.id, ArticleRow.category.is_(None))
                        .values(category=category)
                    )
                    changed += cast(CursorResult[Any], result).rowcount
        return {"applied": apply, "changed": changed, "preview": dict(counts)}
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.apply))))


if __name__ == "__main__":
    main()
