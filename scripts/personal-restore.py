"""Restore a personal snapshot into NEW directories; leaves application stopped.

Stop the old Compose stack first. Requires Docker and the pinned gVisor runtime
already installed. No overwrite of existing data and no paid model requests.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--source-dir', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'posix' or os.getuid() == 0:
        raise SystemExit('Run as the non-root deployment owner')
    snapshot = args.snapshot.resolve(strict=True)
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    expected = {'configuration.tar.gz', 'database.dump', 'images.tar.gz', 'source.tar'}
    if manifest.get('format') != 1 or set(manifest['artifacts']) != expected:
        raise SystemExit('Unsupported snapshot')
    for name, metadata in manifest['artifacts'].items():
        path = snapshot / name
        if path.is_symlink() or path.stat().st_size != metadata['bytes']:
            raise SystemExit('Snapshot integrity failure')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != metadata['sha256']:
                raise SystemExit('Snapshot checksum failure')
    for path in [args.data_dir, args.source_dir]:
        if not path.is_absolute() or path != path.resolve() or path.exists():
            raise SystemExit('New canonical destination directories required')
        if path.parent.stat().st_uid != os.getuid():
            raise SystemExit('Deployment-owner destination parent required')
    if args.data_dir == args.source_dir or args.data_dir.is_relative_to(args.source_dir) or args.source_dir.is_relative_to(args.data_dir):
        raise SystemExit('Separate data and source destinations required')
    running = run(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + manifest['stack']], capture_output=True, text=True).stdout.strip()
    if running:
        raise SystemExit('Stop the old stack before restoring its identity and quota ledger')
    os.umask(0o077)
    for archive_name, target in [('configuration.tar.gz', args.data_dir), ('source.tar', args.source_dir)]:
        target.mkdir(mode=0o700)
        with tarfile.open(snapshot / archive_name) as archive:
            archive.extractall(target, filter='data')
    data = args.data_dir
    stack = json.loads((data / 'compose.json').read_text())
    old_data = Path(next(s['file'] for s in stack['secrets'].values())).parent.parent
    for service in stack['services'].values():
        if service['user'] != f'{os.getuid()}:{os.getgid()}':
            raise SystemExit('Restore using the original deployment UID/GID')
        service['build']['context'] = str(args.source_dir)
        if 'group_add' in service:
            service['group_add'] = [str(Path('/run/docker.sock').stat().st_gid)]
        for mount in service.get('volumes', []):
            old = Path(mount['source'])
            if mount['target'] == '/opt/radar-embedding':
                mount['source'] = str(data / 'embedding')
            elif old.is_relative_to(old_data):
                mount['source'] = str(data / old.relative_to(old_data))
    for secret in stack['secrets'].values():
        secret['file'] = str(data / Path(secret['file']).relative_to(old_data))
    for name in ['database', 'service_locks', 'sandbox_locks', 'archive_reports']:
        (data / name).mkdir(mode=0o700)
    config = data / 'compose.json'
    config.write_text(json.dumps(stack, indent=2) + '\n')
    run(['docker', 'image', 'load', '-i', str(snapshot / 'images.tar.gz')], stdout=subprocess.DEVNULL)
    for name, identity in manifest['image_ids'].items():
        actual = run(['docker', 'image', 'inspect', '-f', '{{.Id}}', name], capture_output=True, text=True).stdout.strip()
        if actual != identity:
            raise SystemExit('Restored image ID mismatch')
    compose = ['docker', 'compose', '-f', str(config), '--profile', 'active']
    run(compose + ['up', '-d', '--no-build', '--wait', 'db'])
    database = run(compose + ['ps', '-q', 'db'], capture_output=True, text=True).stdout.strip()
    with (snapshot / 'database.dump').open('rb') as stream:
        toc = run(['docker', 'exec', '-i', database, 'pg_restore', '--list'], stdin=stream, capture_output=True).stdout.decode()
    lines = [line for line in toc.splitlines() if not any(x in line for x in [
        ' SCHEMA - public ', ' EXTENSION - vector ', ' COMMENT - EXTENSION vector ', ' COMMENT - SCHEMA public ',
    ])]
    run(['docker', 'exec', '-i', database, 'tee', '/tmp/restore.list'],
        input=('\n'.join(lines) + '\n').encode(), stdout=subprocess.DEVNULL)
    with (snapshot / 'database.dump').open('rb') as stream:
        run(['docker', 'exec', '-i', database, 'pg_restore', '-U', 'radar_bootstrap',
             '-d', 'ai_radar', '--role=radar_owner', '--no-owner', '--no-acl',
             '--exit-on-error', '--use-list=/tmp/restore.list'], stdin=stream)
    run(compose + ['run', '--rm', '--no-deps', 'migrate'])
    print(json.dumps({'restored': True, 'compose': str(config), 'application_started': False,
                      'paid_extraction_started': False, 'paid_calls': 0}))


if __name__ == '__main__':
    main()
