#!/usr/bin/env bash
# Operator-only Ubuntu installation. Never called by the Agent or public API.
# Inspect this file, then run with sudo; only adds a named runtime and reloads Docker.
set -Eeuo pipefail

if [[ ${EUID} -ne 0 || $(uname -m) != x86_64 ]]; then
  echo 'Requires an Ubuntu x86_64 administrator; no changes made.' >&2
  exit 1
fi

archive=/home/xvsf/ai-radar/.run/gvisor-20260907.0/gvisor.tar.bz2
release=/opt/ai-radar/gvisor/20260907.0
expected=c38cc38ee709d862501e55eebd99f5bd105899cbc7cf3fa1f620493fa127364c5b74c7361d231bd8b9523be48918ea3820dd40b28c61c2b2cb644edbf10261fb
config=/etc/docker/daemon.json
exec 9>/run/lock/ai-radar-gvisor-install.lock
flock -n 9 || { echo 'Another installation is in progress.' >&2; exit 1; }
test -f "$archive"
test ! -e "$release"
test ! -L "$release"
test ! -L "$config"
command -v python3 >/dev/null
command -v dockerd >/dev/null
systemctl is-active --quiet docker

# Fail before installing if an existing runtime already owns this name.
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/etc/docker/daemon.json')
config = json.loads(p.read_text()) if p.exists() else {}
if 'runsc' in config.get('runtimes', {}):
    raise SystemExit('runsc is already configured; review instead of overwriting it.')
for folder in ('/opt', '/opt/ai-radar', '/opt/ai-radar/gvisor', '/etc/docker', '/var/backups'):
    p = Path(folder)
    if p.is_symlink() or (p.exists() and (p.stat().st_uid != 0 or p.stat().st_mode & 0o022)):
        raise SystemExit('Untrusted installation parent: ' + folder)
PY

backup=$(mktemp -d /var/backups/ai-radar-gvisor-20260907.0-XXXXXXXX)
chmod 700 "$backup"
# Check a root-owned private snapshot, avoiding modification between hash and extraction.
install -m 600 "$archive" "$backup/gvisor.tar.bz2"
printf '%s  %s\n' "$expected" "$backup/gvisor.tar.bz2" | sha512sum --check --status
had_config=0
if [[ -f "$config" ]]; then
  cp --preserve=mode,ownership,timestamps "$config" "$backup/daemon.json.before"
  had_config=1
else
  touch "$backup/daemon.json.was-absent"
fi
changed=0
rollback() {
  result=$?
  trap - EXIT
  if [[ $result -ne 0 && $changed -eq 1 ]]; then
    if [[ $had_config -eq 1 ]]; then
      cp --preserve=mode,ownership,timestamps "$backup/daemon.json.before" "$config"
    else
      rm -f -- "$config"
    fi
    systemctl reload docker || echo 'Docker reload failed; administrator must inspect service.' >&2
  fi
  if [[ $result -ne 0 ]]; then
    echo "Installation did not complete. Backup: $backup; partial runtime may remain at $release." >&2
  fi
  exit "$result"
}
trap rollback EXIT

install -d -m 755 /opt/ai-radar/gvisor "$release"
# The archive is fixed by the SHA-512 above and its six entries were independently audited.
tar --extract --bzip2 --file "$backup/gvisor.tar.bz2" --directory "$release" \
    --no-same-owner --no-same-permissions
chmod 755 "$release" "$release/runsc" "$release/containerd-shim-runsc-v1" "$release/gvisor-bin"
chmod 755 "$release"/gvisor-bin/*
"$release/runsc" --version

python3 - "$backup/daemon.json.next" <<'PY'
import json
import os
import sys
from pathlib import Path
p = Path('/etc/docker/daemon.json')
config = json.loads(p.read_text()) if p.exists() else {}
if 'runsc' in config.get('runtimes', {}):
    raise SystemExit('Runtime configuration changed during installation.')
config.setdefault('runtimes', {})['runsc'] = {
    'path': '/opt/ai-radar/gvisor/20260907.0/runsc',
    'runtimeArgs': ['--platform=systrap'],
}
with open(sys.argv[1], 'x', encoding='utf-8') as output:
    json.dump(config, output, indent=2)
    output.write('\n')
    output.flush()
    os.fsync(output.fileno())
PY
dockerd --validate --config-file "$backup/daemon.json.next"
if [[ $had_config -eq 1 ]]; then
  cmp --silent "$config" "$backup/daemon.json.before"
else
  test ! -e "$config"
fi
install -d -m 755 /etc/docker
changed=1
install -m 600 "$backup/daemon.json.next" "$config"
systemctl reload docker
docker --host=unix:///run/docker.sock info --format '{{json .Runtimes}}' |
  python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["runsc"]["path"] == "/opt/ai-radar/gvisor/20260907.0/runsc"'
echo "gVisor runtime installed. Existing default runtime unchanged. Backup: $backup"
echo 'Public Python remains disabled pending isolation acceptance tests.'
