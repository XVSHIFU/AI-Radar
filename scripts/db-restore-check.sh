#!/usr/bin/env bash
# Restore only into a newly created throwaway database, never the application DB.
set -euo pipefail
cd "$(dirname "$0")/.."
archive="${1:?Pass a backup created by scripts/db-backup.sh}"
test -f "$archive"
database="radar_restore_$(date -u +%Y%m%d%H%M%S)_$$"
[[ "$database" =~ ^radar_restore_[0-9]+_[0-9]+$ ]]
docker compose -p ai-radar exec -T db sh -c \
  'createdb -U "$POSTGRES_USER" "$1"' sh "$database"
cleanup() {
  docker compose -p ai-radar exec -T db sh -c \
    'dropdb -U "$POSTGRES_USER" "$1"' sh "$database"
}
trap cleanup EXIT
docker compose -p ai-radar exec -T db sh -c \
  'pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d "$1"' \
  sh "$database" < "$archive"
docker compose -p ai-radar exec -T db sh -c \
  'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -c "
    SELECT version_num FROM alembic_version;
    SELECT (SELECT count(*) FROM sources) AS sources,
           (SELECT count(*) FROM articles) AS articles,
           (SELECT count(*) FROM article_versions) AS versions,
           (SELECT count(*) FROM article_candidates) AS candidates,
           (SELECT count(*) FROM events) AS events;
    SELECT extversion FROM pg_extension WHERE extname = '\''vector'\'';"' sh "$database"
docker compose -p ai-radar exec -T db sh -c \
  'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$database" \
  < scripts/restore-invariants.sql
printf 'Restore check passed; temporary database %s will be removed.\n' "$database"
