# Retrieval performance validation

Measured on 2026-09-15 in disposable `radar_test_*` PostgreSQL 16 + pgvector
databases on the 8 vCPU / 7.2 GiB Ubuntu VM. Each fixture issued 20 concurrent
cold requests and was deleted after the run.

| Fixture | Strict list p95 | Keyword p95 | Observation |
| ---: | ---: | ---: | --- |
| 10,000 events, initial implementation | 5.45 s | 4.30 s | full ORM materialization and application JSON decoding |
| 10,000 events, SQL snapshot + ID-first search | 0.465 s | 0.588 s | exact totals and complete immutable snapshot preserved |
| 100,000 events, diagnostic run | 1.972 s | 4.587 s | full snapshot aggregation and exact hard-scope ID enumeration dominate |

The 10k result improves list latency by 91.5% and keyword latency by 86.3%.
The 100k run is diagnostic evidence, not a claimed service objective.

The benchmark is reproducible with
`tests/integration/test_retrieval_performance.py`. Set
`RADAR_RUN_POSTGRES_TESTS=1`, `RADAR_RUN_PERFORMANCE_TESTS=1`, and optionally
`RADAR_PERFORMANCE_EVENT_COUNT` (default 10000). The harness accepts only
loopback servers and disposable `radar_test_*` databases.

Strict pagination stores the entire ordered public event representation as JSONB in
PostgreSQL. Subsequent pages slice JSONB in SQL and decode only the requested page.
A statement-level revision trigger invalidates snapshot reuse after any event/entity
change; an advisory transaction lock shares one immutable snapshot across concurrent
identical first-page requests. Hybrid search enumerates only IDs for the exact hard
scope, then loads entities for the final ranked page.
