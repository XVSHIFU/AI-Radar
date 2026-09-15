#!/usr/bin/env bash
# Install only after upgrading the database to 0013 or newer.
set -euo pipefail
cd "$(dirname "$0")/.."
checkout="$PWD"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ai-radar-quota-cleanup.service" <<EOF
[Unit]
Description=AI Radar expired quota identity cleanup
After=network-online.target
[Service]
Type=oneshot
WorkingDirectory=$checkout
ExecStart=$checkout/backend/.venv/bin/python -m radar.public_quota_cleanup
TimeoutStartSec=30
UMask=0077
NoNewPrivileges=true
EOF
cat > "$HOME/.config/systemd/user/ai-radar-quota-cleanup.timer" <<EOF
[Unit]
Description=AI Radar quota retention schedule
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now ai-radar-quota-cleanup.timer
