# Research runtime (candidate)

Runs the real `@earendil-works/pi-agent-core` 0.85.1 in fresh per-request instances. Dependency versions and integrity hashes are pinned in `pnpm-lock.yaml`; installation scripts are disabled.

```sh
pnpm install --frozen-lockfile --ignore-scripts
pnpm typecheck
pnpm test  # builds JavaScript first
```

Node >=22.19.0 is required. Only this package's fixed tool definitions are registered; no coding CLI, default file/bash/edit tools, auto-discovery, plugin installation or persistent conversation store is invoked. pi's package includes additional library exports; their presence is not permission to expose them to the model. Python is deliberately absent until its separate isolation gate is verified.

The internal service reads only the packaged `../research/SYSTEM.md`. Configure `RADAR_RUNTIME_TOKEN` privately and start with `pnpm start`. It binds to loopback port 8081 by default. `RADAR_BROKER_ORIGIN` is deployment-owned, never read from request data. The service has no provider API key.

## Internal protocol

- `POST /v1/run`, runtime authentication in `Authorization: Bearer …`.
- Exact body: `prompt`, `max_output` (1–2000), `capability` (an opaque expiring capability issued by the application for one admitted run).
- NDJSON events: `turn`, `text`, `tool`, then `result`. `turn` identifies a new model response; the API must treat earlier turns as drafts and only finalize the terminal answer after citation checks. No thinking blocks or raw tool arguments/results are public events.
- The configured broker receives `POST /internal/research/model` and `/internal/research/tool`, authenticated by the run capability. Tool execution is sequential. HTTP redirects are forbidden; streamed lines, aggregate stream size, tool result size and request body size are bounded.
- Model request body contains `context`, `sequence`, `max_output`. The trusted Python gateway must construct/validate authoritative instructions, transcript, scope and tools itself; Node-supplied context must never grant scope or replace system policy.
- Model response NDJSON: `text {text}`, `tool {id,name,arguments}` (fully assembled and validated provider arguments), `usage {input,output}` (null means unknown), `finish {reason:stop|toolUse|length}`. Usage may follow finish; no other content may.
- Tool request body: `name`, `args`, `call_id`; response: `{result:…}`. The gateway binds every call to the active capability and the model-issued call ID and parameters, applies schema/scope/size checks and independently enforces budgets. Unknown or schema-invalid provider calls must produce validated error results and be consumed without running business code.

## What is verified / outstanding

Tests exercise the installed pi core rather than a mock agent loop: dependent tool rounds, real incremental emission, sequential execution, tool/model budgets, extra-field rejection, cancellation, no automatic retries, secret/error filtering, per-run transcript separation, internal HTTP authentication, and broker envelope validation. Broker/provider outputs are controlled fixtures; no production model was called.

This candidate is **not connected to the public assistant**. Pending: Python model proxy and frozen-scope tool implementations; durable multi-call usage integration with public quota; HTTP/SSE bridge and final citation checks; real configured-model tool streaming/usage/cancellation tests; quality comparison before enabling the route. P1's existing answer path remains live.

The per-run Python guard in `backend/src/radar/research_guard.py` is a second, independent enforcement layer. It is not a replacement for PostgreSQL quota: crash/restart revokes capabilities and retains the persistent reservation. Gateway routing must land on the API instance that owns the active run (single instance initially); do not deploy arbitrary load-balanced callbacks without shared run state or sticky routing.

The Python candidate now also includes research_stream.py and research_gateway.py: bounded provider SSE/tool assembly and a trusted session core with server-owned instructions/history/schemas and a required usage-ledger interface. These are not yet mounted HTTP endpoints or concrete scope/accounting adapters. See docs/research-agent-p2-progress.md for validation and remaining integration work.

Deployment runs compiled JavaScript (`pnpm build`, then `pnpm start`), not native TypeScript stripping. The Ubuntu Node 22.22.1 build lacks native TypeScript support; this build step avoids that optional Node feature. The read-only research package must remain a sibling of runtime in the deployed layout.
