"""Local v0.1.0 Docker release helper. Run on a Linux Docker host; never calls a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.release.json"
ASSISTANT = ROOT / "compose.release.assistant.json"
EMBEDDING = ROOT / "compose.release.embedding.json"
HTTPS = ROOT / "compose.release.https.json"
VERSION = "v0.1.0"
UID = GID = 10001
SECRET_NAMES = (
    "db_bootstrap_password", "db_owner_password", "db_api_password",
    "db_ingest_password", "admin_token", "cursor_secret",
    "public_assistant_secret", "runtime_token", "sandbox_token",
)
DATA_DIRS = ("database", "model_config", "gateway_data", "gateway_config", "service_locks")
IMAGES = ("ai-radar-db", "ai-radar-backend", "ai-radar-gateway")


def require_linux() -> None:
    if sys.platform != "linux":
        raise SystemExit("Run this helper on a Linux Docker host")


def data_root(raw: str, *, new: bool = False) -> Path:
    path = Path(raw)
    if not path.is_absolute() or path == Path("/") or ".." in path.parts:
        raise SystemExit("Use an absolute data root without '..'")
    parent = path.parent.resolve(strict=True)
    if parent != path.parent or parent.is_symlink() or parent.stat().st_uid != os.getuid():
        raise SystemExit("Data root parent must be canonical and owned by this user")
    if new and path.exists():
        raise SystemExit("New data root must not exist")
    if not new and (not path.is_dir() or path.is_symlink()):
        raise SystemExit("Initialized data root required")
    return path


def create_layout(root: Path, *, saved_secrets: dict[str, bytes] | None = None) -> None:
    os.umask(0o077)
    root.mkdir(mode=0o700)
    secret_dir = root / "secrets"
    secret_dir.mkdir(mode=0o700)
    for name in DATA_DIRS:
        (root / name).mkdir(mode=0o700)
    for name in SECRET_NAMES:
        value = saved_secrets[name] if saved_secrets is not None else secrets.token_urlsafe(48).encode("ascii")
        if not value or len(value) > 4096 or any(byte < 32 for byte in value):
            raise SystemExit("Invalid saved secret")
        target = secret_dir / name
        with target.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        target.chmod(0o600)


def set_container_ownership(root: Path) -> None:
    # The helper can only see this newly allocated data root. Secret directory
    # remains user-owned so Compose can traverse it; each secret belongs to 10001.
    script = ("chown -R 10001:10001 /data/database /data/model_config "
              "/data/gateway_data /data/gateway_config /data/service_locks; "
              "chown 10001:10001 /data/secrets/*; chmod 0400 /data/secrets/*")
    subprocess.run(["docker", "run", "--rm", "--user", "0:0", "--network", "none",
                    "--mount", f"type=bind,src={root},dst=/data",
                    "--entrypoint", "/bin/sh", f"ai-radar-db:{os.environ.get('RADAR_RELEASE', VERSION)}",
                    "-eu", "-c", script], check=True)


def env(root: Path) -> dict[str, str]:
    values = os.environ.copy()
    values["RADAR_DATA_ROOT"] = str(root)
    values.setdefault("RADAR_RELEASE", VERSION)
    return values


def compose(root: Path, *args: str, input: bytes | None = None, stdout=None, capture=False,
            overlay: Path | None = None) -> subprocess.CompletedProcess:
    files = ["-f", str(COMPOSE)] + (["-f", str(overlay)] if overlay else [])
    return subprocess.run(
        ["docker", "compose", *files, *args], cwd=ROOT,
        env=env(root), input=input, stdout=subprocess.PIPE if capture else stdout,
        check=True,
    )


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup(root: Path, output: Path) -> None:
    if output.exists() or not output.is_absolute() or output.parent.resolve() != output.parent:
        raise SystemExit("Backup output must be a new absolute directory")
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise SystemExit("Backup and live data roots must be separate")
    output.mkdir(mode=0o700)
    with (output / "database.dump").open("xb") as stream:
        compose(root, "exec", "-T", "db", "pg_dump", "-U", "radar_bootstrap",
                "-d", "ai_radar", "-Fc", "--no-owner", "--no-acl", stdout=stream)
    with (output / "configuration.tar.gz").open("xb") as stream:
        subprocess.run(["docker", "run", "--rm", "--user", "0:0", "--network", "none",
                        "--mount", f"type=bind,src={root},dst=/data,readonly",
                        "--entrypoint", "tar", f"ai-radar-db:{env(root)['RADAR_RELEASE']}",
                        "-C", "/data", "-czf", "-", "secrets", "model_config",
                        "gateway_data", "gateway_config"], check=True, stdout=stream)
    files = {name: {"bytes": (output / name).stat().st_size, "sha256": sha256(output / name)}
             for name in ("database.dump", "configuration.tar.gz")}
    (output / "manifest.json").write_text(json.dumps({"format": 1, "release": env(root)["RADAR_RELEASE"],
                                                        "files": files}, indent=2) + "\n")
    print(f"Backup saved to {output}; keep the exported image tar for recovery")


def restore(root: Path, snapshot: Path) -> None:
    manifest = json.loads((snapshot / "manifest.json").read_text())
    if manifest.get("format") != 1 or set(manifest.get("files", {})) != {"database.dump", "configuration.tar.gz"}:
        raise SystemExit("Unsupported backup")
    if manifest.get("release") != os.environ.get("RADAR_RELEASE", VERSION):
        raise SystemExit("Restore requires the matching release image version")
    for name, metadata in manifest["files"].items():
        file = snapshot / name
        if file.is_symlink() or file.stat().st_size != metadata["bytes"] or sha256(file) != metadata["sha256"]:
            raise SystemExit("Backup checksum failed")
    saved: dict[str, bytes] = {}
    with tarfile.open(snapshot / "configuration.tar.gz", "r:gz") as archive:
        names = set(archive.getnames())
        allowed = {"secrets", "model_config", "gateway_data", "gateway_config"}
        if any(name.split("/")[0] not in allowed or Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise SystemExit("Unsafe backup paths")
        for name in SECRET_NAMES:
            entry = archive.getmember("secrets/" + name)
            if not entry.isfile():
                raise SystemExit("Backup secret is not a regular file")
            member = archive.extractfile(entry)
            if member is None:
                raise SystemExit("Backup is missing a secret")
            saved[name] = member.read()
    stack = os.environ.get("RADAR_STACK", "ai-radar-release")
    if subprocess.run(["docker", "ps", "-a", "-q", "--filter",
                       "label=com.docker.compose.project=" + stack],
                      check=True, capture_output=True).stdout.strip():
        raise SystemExit("Restore requires a new RADAR_STACK with no existing containers")
    create_layout(root, saved_secrets=saved)
    with tarfile.open(snapshot / "configuration.tar.gz", "r:gz") as archive:
        for member in archive.getmembers():
            if member.name.startswith("secrets/") or member.name == "secrets":
                continue
            if not member.isfile() and not member.isdir():
                raise SystemExit("Unsupported backup member")
            if member.isdir():
                continue
            target = root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            target.chmod(0o600)
    set_container_ownership(root)
    compose(root, "up", "-d", "--no-build", "--wait", "db")
    dump = (snapshot / "database.dump").read_bytes()
    listing = compose(root, "exec", "-T", "db", "pg_restore", "--list", input=dump, capture=True).stdout.decode()
    filtered = [line for line in listing.splitlines() if not any(text in line for text in (
        " SCHEMA - public ", " EXTENSION - vector ", " COMMENT - EXTENSION vector ", " COMMENT - SCHEMA public "))]
    compose(root, "exec", "-T", "db", "tee", "/tmp/restore.list", input=("\n".join(filtered) + "\n").encode(), stdout=subprocess.DEVNULL)
    compose(root, "exec", "-T", "db", "pg_restore", "-U", "radar_bootstrap", "-d", "ai_radar",
            "--role=radar_owner", "--no-owner", "--no-acl", "--exit-on-error",
            "--use-list=/tmp/restore.list", input=dump)
    compose(root, "run", "--rm", "migrate")
    print(f"Restored database and identity to {root}; app is stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "build", "up", "down", "export", "backup", "restore", "config", "assistant-up", "embedding-up", "https-up"))
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    require_linux()
    root = data_root(args.data_root, new=args.command in {"init", "restore"})
    if args.command == "init":
        compose(root, "build", "db")
        create_layout(root)
        set_container_ownership(root)
        print(f"Initialized {root}; admin token is in {root / 'secrets' / 'admin_token'}")
    elif args.command == "build":
        compose(root, "build", "db", "api", "gateway")
    elif args.command == "up":
        compose(root, "up", "-d", "--no-build", "--wait", "db")
        compose(root, "--profile", "operations", "run", "--rm", "register-sources")
        compose(root, "--profile", "collection", "up", "-d", "--no-build", "--wait",
                "api", "gateway", "worker", "scheduler")
    elif args.command == "https-up":
        if not os.environ.get("RADAR_DOMAIN"):
            raise SystemExit("Set RADAR_DOMAIN before enabling public HTTPS")
        compose(root, "up", "-d", "--no-build", "--wait", "gateway", overlay=HTTPS)
    elif args.command == "assistant-up":
        compose(root, "build", "pi-runtime", overlay=ASSISTANT)
        compose(root, "up", "-d", "--no-build", "--wait", "pi-runtime", "api", overlay=ASSISTANT)
    elif args.command == "embedding-up":
        model = Path(os.environ.get("RADAR_EMBEDDING_MODEL_DIR", ""))
        if not model.is_absolute() or not model.is_dir():
            raise SystemExit("Set RADAR_EMBEDDING_MODEL_DIR to a verified local model directory")
        compose(root, "--profile", "embedding", "build", "api", "embedding-index", overlay=EMBEDDING)
        compose(root, "--profile", "embedding", "up", "-d", "--no-build", "api", "embedding-index", overlay=EMBEDDING)
    elif args.command == "down":
        compose(root, "--profile", "collection", "down")
    elif args.command == "config":
        compose(root, "--profile", "collection", "config", "--quiet")
        compose(root, "config", "--quiet", overlay=ASSISTANT)
        if os.environ.get("RADAR_DOMAIN"):
            compose(root, "config", "--quiet", overlay=HTTPS)
        if os.environ.get("RADAR_EMBEDDING_MODEL_DIR"):
            compose(root, "--profile", "embedding", "config", "--quiet", overlay=EMBEDDING)
    elif args.command == "export":
        if args.output is None or not args.output.is_absolute() or args.output.exists():
            raise SystemExit("--output must be a new absolute image tar path")
        tags = [f"{name}:{env(root)['RADAR_RELEASE']}" for name in IMAGES]
        subprocess.run(["docker", "image", "save", "-o", str(args.output), *tags], check=True)
        print(f"Exported {args.output} sha256={sha256(args.output)}")
    elif args.command == "backup":
        if args.output is None:
            raise SystemExit("--output backup directory required")
        backup(root, args.output)
    elif args.command == "restore":
        if args.snapshot is None:
            raise SystemExit("--snapshot directory required")
        restore(root, args.snapshot.resolve(strict=True))


if __name__ == "__main__":
    main()