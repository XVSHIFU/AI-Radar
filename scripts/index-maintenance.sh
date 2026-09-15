#!/usr/bin/env bash
# CPU-only incremental indexing. No generation provider or paid API is used.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .run/operations
exec 9>.run/operations/embedding-index.lock
flock -n 9 || exit 0
exec backend/.venv/bin/radar-index-embeddings --limit 100
