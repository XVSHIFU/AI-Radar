from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import get_settings
from .date_quality import DateQualityService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run audit of event dates still based on unverified report dates"
    )
    parser.add_argument("--limit", type=int, default=1000)
    return parser


async def _run(limit: int) -> int:
    if limit < 1:
        raise SystemExit("--limit must be positive")
    url = get_settings().sqlalchemy_url()
    if url is None:
        raise SystemExit("PostgreSQL is not configured")
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        rows = await DateQualityService(
            async_sessionmaker(engine, expire_on_commit=False)
        ).audit(limit=limit)
    finally:
        await engine.dispose()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
        print(
            json.dumps(
                {
                    "event_id": str(row.event_id),
                    "current_date": row.current_date,
                    "status": row.status,
                    "candidates": [
                        {
                            "date": candidate,
                            "evidence_id": str(evidence_id),
                            "paragraph_id": paragraph_id,
                        }
                        for candidate, evidence_id, paragraph_id in row.candidates
                    ],
                },
                ensure_ascii=False,
                default=str,
            )
        )
    print(json.dumps({"dry_run": True, "audited": len(rows), "counts": counts}))
    return 0


def main() -> None:
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(_run(args.limit)))


if __name__ == "__main__":
    main()
