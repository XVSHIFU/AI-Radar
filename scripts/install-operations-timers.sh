#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
checkout="$PWD"
mkdir -p "$HOME/.config/systemd/user"
for task in backup health; do
  if [[ "$task" == backup ]]; then
    command="/bin/bash $checkout/scripts/backup-maintenance.sh"
    schedule='OnCalendar=*-*-* 03:30:00'
  else
    command="$checkout/backend/.venv/bin/python $checkout/scripts/operations-check.py"
    schedule='OnUnitActiveSec=5min'
  fi
  cat > "$HOME/.config/systemd/user/ai-radar-$task.service" <<EOF
[Unit]
Description=AI Radar $task verification
After=network-online.target
[Service]
Type=oneshot
WorkingDirectory=$checkout
ExecStart=$command
UMask=0077
EOF
  cat > "$HOME/.config/systemd/user/ai-radar-$task.timer" <<EOF
[Unit]
Description=AI Radar scheduled $task
[Timer]
$schedule
OnBootSec=10min
Persistent=true
[Install]
WantedBy=timers.target
EOF
done
systemctl --user daemon-reload
systemctl --user enable --now ai-radar-backup.timer ai-radar-health.timer
systemctl --user list-timers --no-pager 'ai-radar-backup*' 'ai-radar-health*'
