#!/usr/bin/env bash
# User services survive SSH disconnects. Boot startup requires an active user manager.
set -euo pipefail
cd "$(dirname "$0")/.."
checkout="$(pwd)"
test -x "$checkout/backend/.venv/bin/python"
test -f "$checkout/.env"
mkdir -p "$HOME/.config/systemd/user"
write_unit() {
  local name="$1" directory="$2" command="$3"
  cat > "$HOME/.config/systemd/user/ai-radar-$name.service" <<EOF
[Unit]
Description=AI Radar $name development service
After=network-online.target
[Service]
Type=simple
WorkingDirectory=$directory
ExecStart=$command
Restart=on-failure
RestartSec=5
UMask=0077
[Install]
WantedBy=default.target
EOF
}
write_unit api "$checkout/backend" "$checkout/backend/.venv/bin/uvicorn radar.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1,::1"
write_unit worker "$checkout/backend" "$checkout/backend/.venv/bin/python -m app.worker"
write_unit scheduler "$checkout/backend" "$checkout/backend/.venv/bin/python -m app.scheduler"
write_unit frontend "$checkout/frontend" "$(command -v node) $checkout/frontend/node_modules/vite/bin/vite.js --host 0.0.0.0 --port 5173 --strictPort"
systemctl --user daemon-reload
systemctl --user enable --now ai-radar-api ai-radar-worker ai-radar-scheduler ai-radar-frontend
systemctl --user --no-pager is-active ai-radar-api ai-radar-worker ai-radar-scheduler ai-radar-frontend
