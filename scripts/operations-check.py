"""Read-only runtime/data checks; no article text, credentials or paid requests in output."""
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend' / 'src'))
from radar.config import Settings  # noqa: E402


async def inspect() -> dict:
    report = {'checked_at': datetime.now(UTC).isoformat(), 'alerts': [], 'metrics': {}}
    alerts = report['alerts']
    try:
        with urlopen('http://127.0.0.1:8000/health/ready', timeout=5) as response:
            report['api_ready'] = response.status == 200
    except Exception:
        report['api_ready'] = False
        alerts.append('API readiness failed')
    url = Settings().sqlalchemy_url()
    if not url:
        alerts.append('Database is not configured')
        return report
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("""
                SELECT
                  (SELECT count(*) FROM events WHERE status='published') AS published_events,
                  (SELECT count(*) FROM events WHERE status='published' AND
                    (event_date IS NULL OR date_precision <> 'day' OR to_jsonb(events)->>'date_basis' = 'report_date_unverified' OR to_jsonb(events)->>'date_conflict' = 'true')) AS uncertain_dates,
                  (SELECT count(*) FROM sources WHERE enabled) AS enabled_sources,
                  (SELECT count(*) FROM sources WHERE enabled AND consecutive_failures >= 3) AS failing_sources,
                  (SELECT count(*) FROM ingest_jobs WHERE state IN ('queued','retry_wait')) AS queued_jobs,
                  (SELECT count(*) FROM ingest_jobs WHERE state='running' AND lease_until < now()) AS expired_leases,
                  (SELECT count(*) FROM evidence e JOIN article_versions v ON v.id=e.article_version_id
                    WHERE NOT (v.paragraphs ? e.paragraph_id)
                    OR strpos(coalesce(v.paragraphs ->> e.paragraph_id,''), e.quote_text)=0) AS invalid_evidence,
                  (SELECT count(*) FROM ingest_runs WHERE started_at > now()-interval '24 hours'
                    AND status IN ('partial','failed')) AS incomplete_runs_24h
            """))
            metrics = dict(result.mappings().one())
            report['metrics'] = metrics
            for key in ('failing_sources', 'expired_leases', 'invalid_evidence', 'incomplete_runs_24h'):
                if metrics[key]:
                    alerts.append(f'{key}: {metrics[key]}')
    except Exception as exc:
        # Exception messages may include DSNs or SQL parameters; expose only the class.
        alerts.append(f'Database checks failed: {type(exc).__name__}')
    finally:
        await engine.dispose()
    return report


if __name__ == '__main__':
    result = asyncio.run(inspect())
    output = Path(__file__).resolve().parents[1] / '.run' / 'operations'
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = output / 'status.json.tmp'
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(output / 'status.json')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result['alerts'] else 0)
