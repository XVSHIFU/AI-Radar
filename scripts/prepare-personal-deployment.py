"""Prepare a private same-host container deployment from existing settings.

Run with the existing backend's Python/PYTHONPATH. Never prints secret values,
never overwrites a data directory, and never starts services or calls a model.
"""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--sandbox-image', required=True)
    args = parser.parse_args()
    if os.name != 'posix' or os.getuid() == 0:
        raise SystemExit('Run as the existing non-root deployment user')
    if not re.fullmatch(r'[a-f0-9]{7,40}', args.release):
        raise SystemExit('Immutable source revision required')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', args.sandbox_image):
        raise SystemExit('Immutable sandbox image required')
    source = args.source.resolve(strict=True)
    data = args.data_dir
    backup = args.backup_dir
    for path in (data, backup):
        if not path.is_absolute() or path != path.resolve() or path.exists():
            raise SystemExit('New canonical data and backup directories required')
        if not path.parent.is_dir() or path.parent.stat().st_uid != os.getuid():
            raise SystemExit('Deployment-user-owned parent required')
    if data == backup or data.is_relative_to(backup) or backup.is_relative_to(data):
        raise SystemExit('Separate data and backup directories required')

    from radar.config import Settings
    old = Settings()
    preserved = {
        'admin_token': old.admin_token,
        'cursor_secret': old.cursor_secret,
        'public_assistant_secret': old.public_assistant_secret,
    }
    if any(not value for value in preserved.values()) or not old.model_config_path.is_file():
        raise SystemExit('Existing identity and model configuration required')
    if old.embedding_model_dir is None or not old.embedding_model_dir.is_dir():
        raise SystemExit('Existing embedding model directory required')
    os.umask(0o077)
    data.mkdir(mode=0o700)
    backup.mkdir(mode=0o700)
    names = ('database', 'model_config', 'gateway_data', 'gateway_config',
             'service_locks', 'sandbox_locks', 'archive_reports', 'secrets')
    for name in names:
        (data / name).mkdir(mode=0o700)
    values = {name: secrets.token_urlsafe(48) for name in (
        'db_bootstrap_password', 'db_owner_password', 'db_api_password',
        'db_ingest_password', 'runtime_token', 'sandbox_token', 'watchdog_token',
    )}
    values.update(preserved)
    for name, value in values.items():
        with (data / 'secrets' / name).open('xb') as output:
            output.write(value.encode())
        (data / 'secrets' / name).chmod(0o400)
    shutil.copyfile(old.model_config_path, data / 'model_config/model.json')
    (data / 'model_config/model.json').chmod(0o600)

    substitutions = {
        'RADAR_STACK': 'ai-radar-personal', 'RADAR_RELEASE': args.release,
        'RADAR_SECRET_DIR': str(data / 'secrets'),
        'RADAR_DOCKER_GID': str(Path('/run/docker.sock').stat().st_gid),
        'RADAR_SANDBOX_IMAGE_ID': args.sandbox_image,
        'RADAR_SERVICE_LOCK_VOLUME': 'radar-personal-service-locks',
        'RADAR_SANDBOX_LOCK_VOLUME': 'radar-personal-sandbox-locks',
        'RADAR_HTTPS_PORT': '19443',
        'RADAR_EMBEDDING_MODEL_DIR': str(old.embedding_model_dir.resolve()),
    }
    def expand(match):
        value = match.group(1)
        key = re.split(r':[-?]', value)[0]
        if key in substitutions:
            return substitutions[key]
        if ':-' in value:
            return value.split(':-', 1)[1]
        raise ValueError('Missing deployment metadata: ' + key)
    raw = re.sub(r'\$\{([^}]+)\}', expand, (source / 'compose.agent.json').read_text())
    stack = json.loads(raw)
    uid, gid = os.getuid(), os.getgid()
    for name, service in stack['services'].items():
        service['user'] = f'{uid}:{gid}'
        service['tmpfs'] = [x.replace('uid=10001', f'uid={uid}').replace('gid=10001', f'gid={gid}') for x in service.get('tmpfs', [])]
        service['build']['context'] = str(source)
        mounts = []
        for mount in service.get('volumes', []):
            if isinstance(mount, str):
                parts = mount.split(':')
                mounts.append({'type':'bind', 'source':str(data / parts[0]),
                    'target':parts[1], 'read_only':len(parts) > 2 and parts[2] == 'ro',
                    'bind':{'create_host_path':False}})
            else:
                mounts.append(mount)
        service['volumes'] = mounts
    stack.pop('volumes')
    # Paid ingestion stays paused unless explicitly selected later.
    stack['services']['worker']['profiles'] = ['collection']
    api = stack['services']['api']
    api['environment']['RESEARCH_AGENT_ENABLED'] = 'true'
    api['environment']['EMBEDDING_MODEL_DIR'] = '/opt/radar-embedding'
    api['environment']['EMBEDDING_MODEL_REVISION'] = old.embedding_model_revision
    api['image'] = 'ai-radar-embedding:' + args.release
    api['build']['target'] = 'embedding'
    api['mem_limit'] = '2g'
    api['cpus'] = 2
    api['volumes'].append({'type':'bind', 'source':str(old.embedding_model_dir.resolve()),
        'target':'/opt/radar-embedding', 'read_only':True, 'bind':{'create_host_path':False}})
    gateway = stack['services']['gateway']
    # Validate privately first; publish port 5173 only during the final cutover.
    gateway['ports'] = ['127.0.0.1:15173:8080']
    gateway['healthcheck']['test'] = ['CMD', 'wget', '-q', '--spider', 'http://127.0.0.1:8080/health']
    caddy = '''{
    admin off
    auto_https off
}
:8080 {
    header X-Content-Type-Options nosniff
    header Referrer-Policy same-origin
    header X-Frame-Options DENY
    @backend path /api /api/* /health /health/*
    handle @backend {
        reverse_proxy api:8000 {
            flush_interval -1
        }
    }
    handle {
        root * /srv
        try_files {path} /index.html
        file_server
    }
}
'''
    (data / 'Caddyfile').write_text(caddy)
    gateway['volumes'].append({'type':'bind', 'source':str(data/'Caddyfile'),
        'target':'/etc/caddy/Caddyfile', 'read_only':True, 'bind':{'create_host_path':False}})
    configuration = data/'compose.json'
    configuration.write_text(json.dumps(stack, indent=2) + '\n')
    subprocess.run(['docker', 'compose', '-f', str(configuration), '--profile', 'active',
        '--profile', 'sandbox', 'config', '--quiet'], check=True)
    print(json.dumps({'data_dir':str(data), 'backup_dir':str(backup),
        'compose':str(configuration), 'public_port_enabled':False,
        'paid_extraction_enabled':False, 'credentials_displayed':False}))


if __name__ == '__main__':
    main()
