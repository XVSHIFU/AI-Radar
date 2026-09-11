# Sol backend delivery report

## Delivered

- Persistent PostgreSQL feed-discovery and article-fetch jobs, immutable article versions, cross-source discovery relations, fenced leases, retry/final-timeout handling, and atomic run aggregation. Alembic head is `0003_persistent_article_jobs`; legacy jobs and terminal runs are migrated without deleting audit history.
- Public-fetch transport built on HTTPX and HTTPcore public interfaces. It rejects credentials and every non-global address (including loopback, private, link-local, IPv4-mapped IPv6, multicast, and shared CGNAT space), pins connections to validated IPs, preserves the origin Host/TLS hostname, and applies the same checks on every redirect. `httpx` and `httpcore` are production dependencies.
- Source registration CLI with disabled-by-default entries, repository-unavailable 503 mapping at the connection boundary, and source/run health accounting for fetch and parser failures.
- Deterministic QueryPlanner and `POST /api/v1/query-plan`, reused by `/ask`. It handles business-timezone dates, six controlled categories, confirmed normalized entity aliases, all/any entity matching, explicit-filter precedence, ambiguity/conflict warnings, and public plan details on clarification or unavailable execution. Unknown residual constraints remain visible and cannot produce a false no-answer response.
- The canonical OpenAPI artifact is `contracts/openapi/v1.json`; the obsolete backend-local generated copy was removed.

## Slice validation

Run from `backend` with Python 3.12:

- `uv run ruff check .` passed.
- `uv run mypy src app` passed for 22 source files.
- `uv run pytest -q` passed: 84 tests, with two third-party deprecation warnings.
- The frozen synthetic QueryPlanner HTTP checker passed 24/24 cases with an injected clock and no model or PostgreSQL.
- `uv export --no-dev --no-emit-project` includes `httpx==0.28.1`; root integration performs the separate clean runtime-environment import check.
- `uv run alembic upgrade head --sql` passed through revision `0003_persistent_article_jobs`.

## Verification limits

No live PostgreSQL instance or paid model was used. PostgreSQL migration, locking, concurrency, and persistence behavior were checked offline and through synthetic/fake-session tests, so they are not reported as live database validation. The local network mapped the five real source hosts to non-global addresses; the secure transport correctly rejected them, leaving real public-body retrieval unverified in this environment. Model generation, vector retrieval, full-text ranking, RRF, and publishing remain outside this slice.