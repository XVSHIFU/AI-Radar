"""Save one private same-host Docker deployment snapshot, without model calls.

The output must be a new directory. Docker volumes are backed up with pg_dump,
not by copying live PostgreSQL files. Run as the deployment owner.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-archive', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'posix' or os.getuid() == 0:
        raise SystemExit('Run as the non-root deployment owner')
    data = args.data_dir.resolve(strict=True)
    output = args.output
    if data.stat().st_uid != os.getuid() or data.stat().st_mode & 0o077:
        raise SystemExit('Private deployment-owner data directory required')
    if not output.is_absolute() or output != output.resolve() or output.exists():
        raise SystemExit('A new canonical output directory is required')
    if not output.parent.is_dir() or output.parent.stat().st_uid != os.getuid():
        raise SystemExit('Deployment-owner output parent required')
    if output.is_relative_to(data):
        raise SystemExit('Backup must be outside the live data directory')
    os.umask(0o077)
    output.mkdir(mode=0o700)
    stack = json.loads((data / 'compose.json').read_text())
    compose = ['docker', 'compose', '-f', str(data / 'compose.json')]
    database = run(compose + ['ps', '-q', 'db'], capture_output=True, text=True).stdout.strip()
    if not database:
        raise SystemExit('Running database required')
    with (output / 'database.dump').open('xb') as stream:
        run(['docker', 'exec', database, 'pg_dump', '-U', 'radar_bootstrap',
             '-d', 'ai_radar', '-Fc', '--no-owner', '--no-acl'], stdout=stream)
    images = sorted(set(service['image'] for service in stack['services'].values()))
    sandbox = stack['services']['sandbox-controller']['environment']['RADAR_SANDBOX_IMAGE_ID']
    images.append(sandbox)
    image_ids = {name: run(['docker', 'image', 'inspect', '-f', '{{.Id}}', name],
                          capture_output=True, text=True).stdout.strip() for name in images}
    with gzip.open(output / 'images.tar.gz', 'wb', compresslevel=1) as archive:
        child = subprocess.Popen(['docker', 'image', 'save', *images], stdout=subprocess.PIPE)
        try:
            while chunk := child.stdout.read(1024 * 1024):
                archive.write(chunk)
        finally:
            child.stdout.close()
        if child.wait() != 0:
            raise SystemExit('Image export failed; snapshot is incomplete')
    # Include credentials/policy, gateway state and the public embedding model.
    # No stale process locks and no live PostgreSQL directory are copied.
    with tarfile.open(output / 'configuration.tar.gz', 'w:gz', compresslevel=1) as archive:
        for name in ['compose.json', 'Caddyfile', 'secrets', 'model_config',
                     'agent-policy', 'gateway_data', 'gateway_config']:
            archive.add(data / name, arcname=name)
        model_mount = next(m for m in stack['services']['api']['volumes']
                           if m['target'] == '/opt/radar-embedding')
        archive.add(Path(model_mount['source']), arcname='embedding')
    import shutil
    shutil.copyfile(args.source_archive, output / 'source.tar')
    artifacts = {path.name: {'bytes': path.stat().st_size, 'sha256': digest(path)}
                 for path in output.iterdir() if path.is_file()}
    (output / 'manifest.json').write_text(json.dumps({
        'format': 1, 'stack': stack['name'], 'image_ids': image_ids,
        'artifacts': artifacts, 'same_host_copy': True,
        'paid_extraction_enabled': False,
    }, indent=2) + '\n')
    print(json.dumps({'snapshot': str(output), 'files': sorted(artifacts),
                      'bytes': sum(item['bytes'] for item in artifacts.values()),
                      'paid_calls': 0}))


if __name__ == '__main__':
    main()
