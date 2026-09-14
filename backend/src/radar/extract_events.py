from __future__ import annotations

import argparse
import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import get_settings
from .deepseek_client import DeepSeekClient
from .extraction_service import ExtractionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract publishable AI events from frozen article versions"
    )
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    parser.add_argument("--limit", type=int, required=True)
    return parser


async def _run(date_from: date, date_to: date, limit: int) -> int:
    settings = get_settings()
    url = settings.sqlalchemy_url()
    if url is None:
        raise SystemExit("PostgreSQL is not configured")
    if not settings.llm_api_key:
        raise SystemExit("LLM_API_KEY is not configured")
    engine = create_async_engine(url, pool_pre_ping=True)
    client = DeepSeekClient(
        settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
    )
    try:
        result = await ExtractionService(
            async_sessionmaker(engine, expire_on_commit=False),
            client,
            timezone=settings.business_timezone,
        ).run(date_from, date_to, limit)
    finally:
        await client.close()
        await engine.dispose()
    print(
        f"claimed={result.claimed} published={result.published} filtered={result.filtered} "
        f"failed={result.failed} stopped={str(result.stopped).lower()}"
    )
    return 2 if result.stopped else 0


def main() -> None:
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(_run(args.date_from, args.date_to, args.limit)))


if __name__ == "__main__":
    main()
