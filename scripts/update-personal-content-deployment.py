"""Review or apply an additive update to the existing personal Compose stack.

Dry run by default. Run as the non-root deployment owner; no model calls.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import time


DATA_DIR = Path("/home/xvsf/ai-radar-data")
BACKUP_ROOT = Path("/home/xvsf/ai-radar-backup")
IMAGES = {
    "api": ("embedding", "embedding"),
    "migrate": ("backend", "backend"),
    "quota-cleaner": ("backend", "backend"),
    "worker": ("backend", "backend"),
    "history-extract": ("backend", "backend"),
    "pi-runtime": ("pi", None),
    "gateway": ("gateway", None),
}
BUILDS = (
    ("backend", "deploy/containers/Backend.Dockerfile", "backend"),
    ("embedding", "deploy/containers/Backend.Dockerfile", "embedding"),
    ("pi", "deploy/containers/Runtime.Dockerfile", None),
    ("gateway", "deploy/containers/Gateway.Dockerfile", None),
)


def run(*args: str, quiet: bool = False, **kwargs):
    return subprocess.run(
        args, check=True, timeout=kwargs.pop("timeout", 3600 if args[:2] == ("docker", "build") else 120),
        stdout=kwargs.pop("stdout", subprocess.DEVNULL if quiet else None),
        stderr=kwargs.pop("stderr", subprocess.DEVNULL if quiet else None), **kwargs,
    )


def compose(path: Path, *args: str, quiet: bool = False):
    return run("docker", "compose", "-f", str(path), *args, quiet=quiet)


def upgraded(old: dict, source: Path, tag: str) -> dict:
    if old.get("name") != "ai-radar-personal":
        raise ValueError("unexpected Compose stack name")
    services = old["services"]
    if set(IMAGES) - services.keys() or "db" not in services or "sandbox-controller" not in services:
        raise ValueError("required services missing")
    if "collection" not in services["worker"].get("profiles", []):
        raise ValueError("worker is not isolated behind collection profile")
    if "paid-extraction" not in services["history-extract"].get("profiles", []):
        raise ValueError("paid extraction profile missing")
    new = copy.deepcopy(old)
    for name, (image, target) in IMAGES.items():
        service = new["services"][name]
        if not isinstance(service.get("build"), dict):
            raise ValueError(f"build definition missing: {name}")
        service["image"] = f"ai-radar-{image}:{tag}"
        service["build"]["context"] = str(source)
        if service["build"].get("target") != target:
            raise ValueError(f"unexpected build target: {name}")
    for name in ("db", "sandbox-controller", "sandbox-watchdog"):
        if new["services"][name] != old["services"][name]:
            raise ValueError(f"protected service changed: {name}")
    return new


def image_builds(source: Path, tag: str, skip: bool):
    for image, dockerfile, target in BUILDS:
        name = f"ai-radar-{image}:{tag}"
        if skip:
            run("docker", "image", "inspect", name, quiet=True)
        else:
            command = ["docker", "build", "-f", str(source / dockerfile), "-t", name]
            if target:
                command += ["--target", target]
            run(*command, str(source))


def running(config: Path, service: str) -> bool:
    # Docker labels include services hidden by inactive Compose profiles.
    result = subprocess.run(
        ["docker", "ps",
         "--filter", "label=com.docker.compose.project=ai-radar-personal",
         "--filter", f"label=com.docker.compose.service={service}",
         "--format", "{{.ID}}"],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return bool(result.stdout.strip())


def health(config: Path, service: str) -> bool:
    checks = {
        "api": ["python", "-c", "import json,urllib.request; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=3)); assert r['status']=='ready'"],
        "pi-runtime": ["node", "-e", "fetch('http://127.0.0.1:8081/health').then(r=>r.json()).then(j=>{if(j.status!=='ready')process.exit(1)}).catch(()=>process.exit(1))"],
        "gateway": ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/health"],
    }
    try:
        compose(config, "exec", "-T", service, *checks[service], quiet=True)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def wait_healthy(config: Path, service: str):
    for _ in range(24):
        if health(config, service):
            return
        time.sleep(3)
    raise RuntimeError(f"{service} health gate failed")


def start(config: Path, service: str):
    compose(config, "up", "-d", "--no-deps", "--no-build", "--force-recreate", service)


def db_scalar(container: str, sql: str) -> str:
    return subprocess.run(
        ["docker", "exec", container, "psql", "-U", "radar_bootstrap",
         "-d", "ai_radar", "-At", "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout.strip()


def rollback_allowed(container: str) -> bool:
    # 0014 creates four empty work tables and one fixed settings seed row.
    sql = (
        "SELECT (SELECT count(*) FROM content_tasks)=0 AND "
        "(SELECT count(*) FROM content_drafts)=0 AND "
        "(SELECT count(*) FROM content_batches)=0 AND "
        "(SELECT count(*) FROM content_usage)=0 AND "
        "(SELECT count(*) FROM content_settings)=1 AND "
        "(SELECT count(*) FROM content_settings WHERE id=1 AND enabled=false "
        "AND auto_publish=false AND batch_limit=5 AND daily_article_limit=0 "
        "AND daily_input_tokens=0 AND daily_output_tokens=0 "
        "AND article_max_calls=1 AND max_output_tokens=1600 "
        "AND concurrency=1 AND profile='{}'::jsonb AND profile_version=1)=1"
    )
    return db_scalar(container, sql) == "t"


def downgrade_empty_content(config: Path):
    command = (
        "import os,sys;from radar.container_entry import environment;"
        "e=environment('migrate',os.environ);os.environ.clear();os.environ.update(e);"
        "os.execv(sys.executable,[sys.executable,'-m','alembic','downgrade',"
        "'0013_public_quota_retention'])"
    )
    compose(config, "run", "--rm", "--no-deps", "--entrypoint", "python",
            "migrate", "-c", command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--backup-root", type=Path, default=BACKUP_ROOT)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Build, back up, migrate, and switch services")
    args = parser.parse_args()
    if os.name != "posix" or os.getuid() == 0:
        parser.error("run as the non-root deployment owner on Ubuntu")
    if not re.fullmatch(r"[a-f0-9]{7,40}", args.tag):
        parser.error("tag must be an immutable Git revision")
    source = args.source_dir.resolve(strict=True)
    data = args.data_dir.resolve(strict=True)
    backup_root = args.backup_root.resolve(strict=True)
    if not (source / "deploy/containers/Backend.Dockerfile").is_file():
        parser.error("source archive is incomplete")
    if data.stat().st_uid != os.getuid() or data.stat().st_mode & 0o077:
        parser.error("private deployment-owner data directory required")
    if backup_root.stat().st_uid != os.getuid():
        parser.error("deployment-owner backup root required")
    config = data / "compose.json"
    if config.is_symlink() or config.stat().st_uid != os.getuid():
        parser.error("owned regular Compose file required")
    before = config.read_bytes()
    old = json.loads(before)
    proposed = upgraded(old, source, args.tag)
    backup = backup_root / f"pre-content-{args.tag}"
    if backup.exists() or backup.is_relative_to(data):
        parser.error("unique backup directory outside live data required")
    print(json.dumps({
        "mode": "apply" if args.apply else "dry_run",
        "stack": old["name"], "source": str(source), "backup": str(backup),
        "images": [f"ai-radar-{name}:{args.tag}" for name, _, _ in BUILDS],
        "replaced_services": list(IMAGES),
        "active_restart": ["pi-runtime", "api", "quota-cleaner", "gateway"],
        "collection_and_paid_extraction": "remain_stopped",
    }))
    if not args.apply:
        return
    for idle in ("worker", "history-extract", "scheduler", "history-discover",
                 "embedding-index", "embedding-activate"):
        if running(config, idle):
            raise SystemExit(f"{idle} must be stopped before upgrade")
    db = subprocess.run(
        ["docker", "compose", "-f", str(config), "ps", "--status", "running", "-q", "db"],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    if not db or db_scalar(db, "SELECT version_num FROM alembic_version") != "0013_public_quota_retention":
        raise RuntimeError("running database at 0013 required")
    image_builds(source, args.tag, args.skip_build)
    os.umask(0o077)
    backup.mkdir(mode=0o700)
    (backup / "compose.before.json").write_bytes(before)
    with (backup / "database.dump").open("xb") as dump:
        run("docker", "exec", db, "pg_dump", "-U", "radar_bootstrap",
            "-d", "ai_radar", "-Fc", "--no-owner", "--no-acl", stdout=dump, timeout=900)
    candidate = data / f"compose.next-{args.tag}.json"
    candidate.write_text(json.dumps(proposed, indent=2) + "\n", encoding="utf-8")
    compose(candidate, "config", "--quiet", quiet=True)
    try:
        # Keep public traffic away from the new tables until all health gates pass.
        compose(config, "stop", "gateway", "api", "quota-cleaner")
        os.replace(candidate, config)
        compose(config, "run", "--rm", "--no-deps", "migrate")
        start(config, "pi-runtime")
        wait_healthy(config, "pi-runtime")
        start(config, "api")
        wait_healthy(config, "api")
        start(config, "quota-cleaner")
        start(config, "gateway")
        wait_healthy(config, "gateway")
        for idle in ("worker", "history-extract"):
            if running(config, idle):
                raise RuntimeError(f"{idle} unexpectedly started")
    except Exception as failure:
        compose(config, "stop", "gateway", "api", "quota-cleaner")
        revision = db_scalar(db, "SELECT version_num FROM alembic_version")
        if revision == "0014_content_workbench":
            if not rollback_allowed(db):
                raise RuntimeError(
                    "0014 has content data or changed settings; gateway must remain stopped, "
                    "manual recovery required"
                ) from failure
            downgrade_empty_content(config)
            revision = db_scalar(db, "SELECT version_num FROM alembic_version")
        if revision != "0013_public_quota_retention":
            raise RuntimeError(
                f"schema {revision!r} cannot use old images; manual recovery required"
            ) from failure
        restore = data / f"compose.rollback-{args.tag}.json"
        restore.write_bytes(before)
        os.replace(restore, config)
        for service in ("pi-runtime", "api", "quota-cleaner", "gateway"):
            start(config, service)
        for service in ("pi-runtime", "api", "gateway"):
            wait_healthy(config, service)
        raise RuntimeError("upgrade failed; old Compose and schema restored") from failure
    print(json.dumps({"status": "healthy", "tag": args.tag,
                      "pre_upgrade_backup": str(backup), "paid_calls": 0}))


if __name__ == "__main__":
    main()
