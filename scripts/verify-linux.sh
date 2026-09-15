#!/usr/bin/env bash
# Paid providers are never used by this suite; PostgreSQL tests create isolated databases.
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
# User-local tool installation used by the Ubuntu development services.
if ! command -v pnpm >/dev/null && [[ -x "$HOME/.local/share/ai-radar-tools/node_modules/.bin/pnpm" ]]; then
  export PATH="$HOME/.local/share/ai-radar-tools/node_modules/.bin:$PATH"
fi
if [[ "${1:-}" == --postgres ]]; then export RADAR_RUN_POSTGRES_TESTS=1; fi
cd backend
uv run --frozen ruff check .
uv run --frozen mypy src app
uv run --frozen pytest -q
uv run --frozen python ../scripts/check-database-unavailable.py
uv run --frozen python ../scripts/check-structure.py
uv run --frozen python ../scripts/check-query-plan.py
uv run --frozen python ../scripts/freeze-openapi.py
cd "$root/frontend"
pnpm typecheck
pnpm test
pnpm build
printf 'Verification passed (PostgreSQL opt-in: %s; paid model calls: none).\n' "${RADAR_RUN_POSTGRES_TESTS:-0}"
