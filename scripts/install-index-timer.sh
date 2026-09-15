#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
checkout="$PWD"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ai-radar-index.service" <<EOF
[Unit]
Description=AI Radar incremental CPU embedding index
After=network-online.target
[Service]
Type=oneshot
WorkingDirectory=$checkout
ExecStart=/bin/bash $checkout/scripts/index-maintenance.sh
TimeoutStartSec=15min
MemoryMax=2G
UMask=0077
EOF
cat > "$HOME/.config/systemd/user/ai-radar-index.timer" <<'EOF'
[Unit]
Description=AI Radar scheduled incremental vector indexing
[Timer]
OnBootSec=15min
OnUnitActiveSec=15min
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now ai-radar-index.timer
systemctl --user list-timers --no-pager ai-radar-index.timer
