#!/usr/bin/env bash
# Run as the sandbox service user. Only its labelled, expired tasks are eligible.
set -Eeuo pipefail
radar_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
radar_python=${RADAR_PYTHON_BIN:-"$radar_root/backend/.venv/bin/python"}
test -x "$radar_python"
test -f "$radar_root/backend/src/radar/sandbox_reaper.py"
radar_units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$radar_units"
cat > "$radar_units/ai-radar-sandbox-watchdog.service" <<EOF
[Unit]
Description=AI Radar expired Python sandbox cleanup

[Service]
Type=oneshot
Environment="PYTHONPATH=$radar_root/backend/src"
ExecStart="$radar_python" -m radar.sandbox_reaper
NoNewPrivileges=true
TimeoutStartSec=22
MemoryMax=192M
CPUQuota=25%
KillMode=control-group
EOF
cat > "$radar_units/ai-radar-sandbox-watchdog.timer" <<'EOF'
[Unit]
Description=AI Radar independent Python sandbox watchdog

[Timer]
OnBootSec=5s
OnUnitActiveSec=5s
AccuracySec=1s
Unit=ai-radar-sandbox-watchdog.service

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now ai-radar-sandbox-watchdog.timer
systemctl --user start ai-radar-sandbox-watchdog.service
systemctl --user is-active ai-radar-sandbox-watchdog.timer
