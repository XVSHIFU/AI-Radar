#!/usr/bin/env bash
# Managed private backup set: database plus local runtime configuration, retained 14 days.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
archive="$(bash scripts/db-backup.sh)"
config_archive="${archive%.dump}.config.tar"
files=()
[[ -f .env ]] && files+=(.env)
[[ -f "$HOME/.config/ai-radar/model.json" ]] && files+=("$HOME/.config/ai-radar/model.json")
if ((${#files[@]})); then tar -czf "$config_archive" -- "${files[@]}"; fi
sha256sum "$archive" > "$archive.sha256"
# Verification uses a disposable database and never restores over the live database.
bash scripts/db-restore-check.sh "$archive"
find .run/backups -maxdepth 1 -type f -name 'radar-*.dump' -mtime +14 -delete
find .run/backups -maxdepth 1 -type f -name 'radar-*.dump.sha256' -mtime +14 -delete
find .run/backups -maxdepth 1 -type f -name 'radar-*.config.tar' -mtime +14 -delete
printf 'Verified private backup: %s\n' "$archive"
