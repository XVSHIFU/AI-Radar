# Retrieval performance baseline

Measured on 2026-09-15 in a disposable `radar_test_*` PostgreSQL 16 + pgvector
database on the 8 vCPU / 7.2 GiB Ubuntu VM. The fixture contained 10,000 published
events and issued 20 concurrent cold requests. The database was deleted after the run.

| Operation | Measured p95 | Initial specification example | Result |
| --- | ---: | ---: | --- |
| strict event list with frozen full-result snapshot | 5.45 s | 300 ms | not met |
| hard-scoped keyword search with exact scope count | 4.30 s | 500 ms | not met |

The benchmark is reproducible with the gated
`tests/integration/test_retrieval_performance.py` test. Set both
`RADAR_RUN_POSTGRES_TESTS=1` and `RADAR_RUN_PERFORMANCE_TESTS=1`; the shared test
harness refuses non-loopback servers and database names outside `radar_test_*`.

Correctness remains the current priority. The first-page strict snapshot materializes
the complete frozen response, which dominates this baseline under concurrency. Future
optimization must preserve frozen content and exact totals; using a created-at cutoff or
semantic top-k as a substitute is not acceptable.
