from __future__ import annotations

import argparse
import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import get_settings
from .deepseek_client import DeepSeekClient
from .extraction_service import ExtractionService
from .ingest.dns import configured_resolver
from .model_config import ModelConfigStore, ModelConfigUnavailable


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
    try:
        model_config = ModelConfigStore(settings).read()
    except ModelConfigUnavailable as exc:
        raise SystemExit(str(exc)) from exc
    if not model_config.enabled:
        print("claimed=0 published=0 filtered=0 failed=0 stopped=false")
        return 0
    if not model_config.api_key:
        raise SystemExit("LLM_API_KEY is not configured")
    engine = create_async_engine(url, pool_pre_ping=True)
    client = DeepSeekClient(
        model_config.api_key,
        base_url=model_config.base_url,
        model=model_config.model,
        provider=model_config.provider,
        resolver=configured_resolver(settings.fetch_dns_mode),
        max_tokens=model_config.max_tokens,
    )
    try:
        result = await ExtractionService(
            async_sessionmaker(engine, expire_on_commit=False),
            client,
            timezone=settings.business_timezone,
            credential_changed_at=model_config.credential_changed_at,
            provider=model_config.provider,
            model=model_config.model,
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
