#!/usr/bin/env bash
# Run from the Ubuntu checkout; backups contain source text and must stay private.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p .run/backups
target=".run/backups/radar-$(date -u +%Y%m%dT%H%M%S)-$$.dump"
docker compose -p ai-radar exec -T db sh -c \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' > "$target.partial"
mv -- "$target.partial" "$target"
printf '%s\n' "$target"
