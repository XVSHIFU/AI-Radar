#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
checkout="$(pwd)"
mkdir -p "$HOME/.config/systemd/user"
for mode in discover extract; do
  interval=1h
  [[ "$mode" == extract ]] && interval=10min
  cat > "$HOME/.config/systemd/user/ai-radar-history-$mode.service" <<EOF
[Unit]
Description=AI Radar historical $mode pass
After=network-online.target
[Service]
Type=oneshot
WorkingDirectory=$checkout
ExecStart=/bin/bash $checkout/scripts/history-pipeline.sh $mode
TimeoutStartSec=infinity
UMask=0077
SuccessExitStatus=2
EOF
  cat > "$HOME/.config/systemd/user/ai-radar-history-$mode.timer" <<EOF
[Unit]
Description=AI Radar recurring historical $mode
[Timer]
OnBootSec=2min
OnUnitInactiveSec=$interval
Persistent=true
Unit=ai-radar-history-$mode.service
[Install]
WantedBy=timers.target
EOF
done
# The historical scanner replaces the unrestricted RSS scheduler for this backfill.
systemctl --user disable --now ai-radar-scheduler
systemctl --user daemon-reload
systemctl --user enable --now ai-radar-history-discover.timer ai-radar-history-extract.timer
systemctl --user list-timers --no-pager 'ai-radar-history-*'
