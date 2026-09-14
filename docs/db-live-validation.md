# PostgreSQL live validation

Validated on Ubuntu against the repository's PostgreSQL 16 + pgvector service. The tests use
randomly named `radar_test_*` databases, require the explicit
`RADAR_RUN_POSTGRES_TESTS=1` opt-in, and refuse to drop any database without that prefix. No
provider API or model was called.

## Configuration result

Alembic now resolves its connection through `Settings`, matching the API, worker, and scheduler.
This removes the prior passwordless `localhost:5432` fallback during normal configured runs.
`Settings.alembic_url()` renders SQLAlchemy `URL` values without password redaction; Alembic then
escapes percent signs for `ConfigParser`. A regression reconstructs a password containing URL and
interpolation special characters and verifies it survives the render/parse round trip. Test output
does not print the configured database URL.

## Live database coverage

The opt-in suite verifies these behaviors against PostgreSQL rather than a fake session:

- Alembic upgrade through `0004_candidate_versions`, pgvector extension presence, downgrade
  to `0002_ingest_pipeline`, preservation of source/run/job rows, and re-upgrade to head.
- `/health/ready` reports PostgreSQL ready only with the expected Alembic revision and vector
  extension.
- Published, day-precision event filtering by date, category, and confirmed subject/product alias;
  exact total across keyset pages; exclusion of draft events and mention-only entity relations.
- Evidence resolution from the specified immutable article version and paragraph, plus rejection of
  an invented quote through the public HTTP error contract.
- Concurrent ingest idempotency and `FOR UPDATE SKIP LOCKED` claims without duplicated work.
- Lease expiry reclaim with an incremented generation, rejection of the stale worker's heartbeat
  and finish, and terminal run failure after the final expired attempt.
- Idempotent budget reservation and serialization of concurrent reservations at the configured
  limit.
- A real-database worker cycle that creates two immutable versions and version-bound candidates for
  changed content, retains the RSS publication date, and creates neither a third version nor a third
  candidate when the body is unchanged.

## Commands and result

Run from the repository root with the backend environment installed and PostgreSQL configured:

```bash
RADAR_RUN_POSTGRES_TESTS=1 \
PYTHONPATH="$PWD/backend/src" \
backend/.venv/bin/python -m pytest -q backend/tests/integration
```

Result on 2026-09-14: **8 passed**. The suite created two disposable test databases and removed both
after completion. Existing application databases and unrelated containers were not modified.

Normal backend checks remain opt-out safe: without `RADAR_RUN_POSTGRES_TESTS=1`, live database tests
skip while the special-character URL regression still runs.

## Deliberate limits

This report validates revisions 0001–0004 at the reviewed checkpoint. Later schema revisions must
extend the migration round-trip expectation before they can be described as live-validated.
Cross-page writes remain outside the current list contract; responses identify that limitation in
their data revision. The suite proves Evidence location and whitelist-compatible response data, not
model support for a claim. Model extraction, event publication, embedding, generated answers,
backup restore, and paid-call accounting remain separate from this test suite.
