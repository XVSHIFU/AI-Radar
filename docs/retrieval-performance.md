# Retrieval performance validation

Measured on 2026-09-15 in disposable `radar_test_*` PostgreSQL 16 + pgvector
databases on the 8 vCPU / 7.2 GiB Ubuntu VM. The fixture uses the complete
0008-0010 migration chain. Each concurrent phase uses 20 requests.

| Fixture and phase | Samples | Strict list p95 | Keyword p95 |
| --- | ---: | ---: | ---: |
| 10,000 events, fully cold pool and cold snapshot | 20 | 0.462 s | - |
| 10,000 events, 20 connections prewarmed, cold snapshot | 20 | 0.240 s | - |
| 10,000 events, existing same-revision snapshot, 5 rounds | 100 | 0.073 s | - |
| 10,000 events, warm pool, 5 rounds | 100 | - | 0.124 s |
| 100,000 events, earlier diagnostic cold run | 20 | 1.974 s | 0.381 s |

The fully cold 10k result remains above the 300 ms list example. Prewarming the
connection pool isolates cold snapshot construction at 240 ms, while snapshot reuse
measures 73 ms at p95. These phases diagnose startup, freeze, and steady-state costs;
the steady-state number does not replace the fully cold result. Warm keyword search
meets the 500 ms example. The 100k run is diagnostic evidence, not a claimed service
objective.

The benchmark is reproducible with
`tests/integration/test_retrieval_performance.py`. Set
`RADAR_RUN_POSTGRES_TESTS=1` and `RADAR_RUN_PERFORMANCE_TESTS=1`. Optionally
set `RADAR_PERFORMANCE_EVENT_COUNT` (default 10000) and
`RADAR_EXPLAIN_SNAPSHOT_PAGE=1`. The harness accepts only loopback servers and
disposable `radar_test_*` databases.

Strict pagination stores the entire ordered public event representation as JSONB in
PostgreSQL. Subsequent pages use a JSONPath array range in SQL and decode only the
requested page. On the 10k fixture, `EXPLAIN (ANALYZE, BUFFERS)` for offset 5000,
limit 20 returned 20 rows in 2.536 ms; the function scan took 2.357 ms. A
statement-level revision trigger invalidates snapshot reuse after any event or entity
change, and an advisory transaction lock shares one immutable snapshot across
concurrent identical first-page requests.

Hybrid search obtains an exact hard-scope count, applies complete hard filters
independently to keyword and semantic SQL in the same repeatable-read transaction,
and loads the frozen public projection only for the final ranked page. FTS candidates
run first through the GIN index; ILIKE fills remaining candidate slots so Chinese
single-character substring behavior is retained.
