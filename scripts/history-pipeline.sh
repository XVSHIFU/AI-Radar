#!/usr/bin/env bash
# Resumable August–September 2026 archive/extraction passes.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p .run
mode="${1:-discover}"
[[ "$mode" == discover || "$mode" == extract ]]
exec 9>".run/history-$mode.lock"
flock -n 9 || exit 0
today="$(TZ=Asia/Shanghai date +%F)"
end="$today"
[[ "$end" > 2026-09-30 ]] && end=2026-09-30
[[ "$end" < 2026-08-01 ]] && exit 0
cd backend
if [[ "$mode" == discover ]]; then
  exec .venv/bin/python -u -m radar.backfill --date-from 2026-08-01 --date-to "$end"
else
  # Provider hard quota controls spending. Authentication/balance failures persist in DB.
  exec .venv/bin/python -u -m radar.extract_events --date-from 2026-08-01 --date-to "$end" --limit 80
fi
