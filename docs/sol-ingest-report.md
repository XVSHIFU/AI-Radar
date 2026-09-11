# Sol ingest pipeline report

## Delivered

- PostgreSQL `0002_ingest_pipeline` migration for persistent ingest runs/jobs, article candidates, LLM-call ledger, budget reservations, RSS source metadata, and immutable article-version deduplication.
- Authenticated `POST/GET /api/v1/ingest/runs`; fixture/no-database mode returns an explicit 503. Idempotency keys are payload-bound and serialized with a PostgreSQL advisory transaction lock.
- Independent APScheduler 3.x scheduler and worker entry points. Jobs use `FOR UPDATE SKIP LOCKED`, owner/generation leases, bounded retry/backoff, terminal failure after the final expired lease, and reject stale completion.
- Free RSS/article fetch path with conditional headers, manual redirect validation, semantic query preservation, tracking-key removal, HTTP(S)-only URLs, credential/private/loopback rejection, response limits, and `trust_env=False`.
- Deterministic paragraph IDs/content hashes, immutable same-URL versions, `needs_review` candidates, exact quote location checks, and citation whitelist validation. No paid model is called and candidates are not counted as published events (`kept=0`).
- Fixture list/detail/evidence counts now match the single frozen synthetic evidence item. PostgreSQL `evidence_for` itself rejects empty, missing, or mismatched quotes.

## Validation

Run from `backend` with Python 3.12:

- `uv sync` — dependency installation and lock update succeeded.
- `uv run ruff check .` — passed.
- `uv run mypy src app` — passed (18 source files).
- `uv run pytest -q` — passed, 32 tests, 2 third-party deprecation warnings, 0.20 s on the final run.
- `uv run alembic upgrade head --sql` — passed; emitted PostgreSQL DDL through `0002_ingest_pipeline` and updated the Alembic revision to that head.
- `uv run python -c "import json; from radar.main import app; ..."` — generated `backend/openapi.generated.json`.
- `git diff --check` — passed; Git only reported future CRLF-to-LF normalization notices.

During this resumed validation there were four failed/retried check cycles: one fixture syntax error caused by a PowerShell newline escape, one outdated API test body, one incorrect fixture test constructor/signature, and one initially missing empty-document guard. All were corrected before the final checks. Work resumed at approximately 01:14 and the final full check completed in roughly 25 minutes.

## Run commands

- API: `$env:RADAR_DATA_MODE='postgres'; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Scheduler: `uv run python -m app.scheduler`
- Worker: `uv run python -m app.worker`

The API, scheduler, and worker require the repository-root database settings. Fixture mode deliberately does not create ingest runs.

## Limits and unverified behavior

No PostgreSQL instance was available. The migration was checked offline and SQL/transaction paths are covered by unit/static checks, but real PostgreSQL locking, advisory-lock concurrency, migration application, pgvector readiness, and end-to-end persistence were not run and are not marked passed.

URL validation resolves and checks every initial/redirect host, rejects non-public results, limits redirects and bytes, and disables environment proxies. `httpx` may resolve again when opening the connection, so a DNS-rebinding window remains until the transport pins the validated address or verifies the connected peer. This implementation does not claim complete SSRF protection across that window.

A real five-feed dry run was not performed in this slice, so no live fetch or parser-success counts are reported.
