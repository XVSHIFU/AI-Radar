"""Private operator recovery bundles. No network, Docker, SQL or model tools.

This module seals already captured artifacts. Capture must supply a consistent
PostgreSQL snapshot; these format checks do not prove that capture happened.
Restoration must verify against a manifest digest kept in a separate inventory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, TypedDict
from uuid import uuid4

SECRET_NAMES = (
    "db_bootstrap_password",
    "db_owner_password",
    "db_api_password",
    "db_ingest_password",
    "admin_token",
    "cursor_secret",
    "public_assistant_secret",
    "runtime_token",
    "sandbox_token",
    "watchdog_token",
)
REQUIRED_FILES = frozenset({"database.dump", "source.tar", "images.tar"}) | frozenset(
    "secrets/" + name for name in SECRET_NAMES
)
OPTIONAL_FILES = frozenset(
    {"model-config.json", "embedding/model.onnx", "embedding/tokenizer.json"}
)
FINGERPRINT_TABLES = frozenset(
    {
        "public_ask_requests",
        "research_model_calls",
        "llm_calls",
        "budget_reservations",
        "events",
        "evidence",
    }
)
IMAGE_ROLES = frozenset({"backend", "db", "pi", "gateway", "controller", "sandbox", "embedding"})
HASH = re.compile(r"[a-f0-9]{64}\Z")
IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z")
MAX_MANIFEST_BYTES = 128 * 1024


class ArtifactRecord(TypedDict):
    bytes: int
    sha256: str


class InvalidBundle(ValueError):
    pass


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise InvalidBundle("invalid recovery metadata")
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise InvalidBundle("invalid recovery digest")
    return value


def _timestamp(value: Any) -> None:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", value
    ):
        raise InvalidBundle("UTC recovery timestamp required")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise InvalidBundle("invalid recovery timestamp") from exc


def validate_manifest(value: Any) -> dict[str, Any]:
    item = _exact(value, {"format", "created_at", "source_commit", "images", "snapshot", "files"})
    if item["format"] != "ai-radar-recovery/1":
        raise InvalidBundle("unsupported recovery format")
    _timestamp(item["created_at"])
    if not isinstance(item["source_commit"], str) or not re.fullmatch(
        "[a-f0-9]{40}", item["source_commit"]
    ):
        raise InvalidBundle("immutable source commit required")
    images = item["images"]
    if (
        not isinstance(images, dict)
        or not {"backend", "db", "pi", "gateway"} <= set(images)
        or not set(images) <= IMAGE_ROLES
        or any(not isinstance(v, str) or not IMAGE.fullmatch(v) for v in images.values())
    ):
        raise InvalidBundle("immutable image IDs required")
    snapshot = _exact(item["snapshot"], {"schema", "captured_at", "snapshot_id", "fingerprints"})
    if snapshot["schema"] != "0013":
        raise InvalidBundle("unsupported recovery schema")
    _timestamp(snapshot["captured_at"])
    if datetime.fromisoformat(snapshot["captured_at"]) > datetime.fromisoformat(item["created_at"]):
        raise InvalidBundle("snapshot cannot be newer than the backup")
    if not isinstance(snapshot["snapshot_id"], str) or not re.fullmatch(
        r"[0-9A-F]{8}-[0-9A-F]{8}-[0-9]+", snapshot["snapshot_id"]
    ):
        raise InvalidBundle("exported PostgreSQL snapshot ID required")
    fingerprints = _exact(snapshot["fingerprints"], set(FINGERPRINT_TABLES))
    for record in fingerprints.values():
        entry = _exact(record, {"rows", "sha256"})
        if type(entry["rows"]) is not int or entry["rows"] < 0:
            raise InvalidBundle("invalid snapshot row count")
        _sha(entry["sha256"])
    files = item["files"]
    if (
        not isinstance(files, dict)
        or not REQUIRED_FILES <= set(files)
        or not set(files) <= REQUIRED_FILES | OPTIONAL_FILES
    ):
        raise InvalidBundle("incomplete recovery files")
    embedded = {name for name in files if name.startswith("embedding/")}
    if embedded and embedded != {"embedding/model.onnx", "embedding/tokenizer.json"}:
        raise InvalidBundle("incomplete embedding artifacts")
    if ("embedding" in images) != bool(embedded):
        raise InvalidBundle("embedding image and artifacts must be captured together")
    for name, record in files.items():
        entry = _exact(record, {"bytes", "sha256"})
        if type(entry["bytes"]) is not int or not 0 < entry["bytes"] <= 2**63 - 1:
            raise InvalidBundle("invalid artifact length")
        if name.startswith("secrets/") and entry["bytes"] > 4096:
            raise InvalidBundle("oversized recovery credential")
        if name == "model-config.json" and entry["bytes"] > 65536:
            raise InvalidBundle("oversized model configuration")
        _sha(entry["sha256"])
    return item


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidBundle("duplicate recovery metadata key")
        result[key] = value
    return result


def _regular(path: Path) -> int:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise InvalidBundle("regular recovery artifact required")
    return info.st_size


@contextmanager
def _open_checked(path: Path, size: int) -> Iterator[BinaryIO]:
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != size:
            raise InvalidBundle("recovery artifact changed")
        yield stream


def _digest(path: Path, size: int) -> str:
    with _open_checked(path, size) as stream:
        digest, remaining = hashlib.sha256(), size
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise InvalidBundle("truncated recovery artifact")
            digest.update(chunk)
            remaining -= len(chunk)
        if stream.read(1):
            raise InvalidBundle("recovery artifact grew")
        return digest.hexdigest()


def _sync_directory(path: Path) -> None:
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _inventory(root: Path) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise InvalidBundle("recovery directory required")
    found: set[str] = set()
    allowed = REQUIRED_FILES | OPTIONAL_FILES | {"manifest.json"}

    def visit(directory: Path) -> None:
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if entry.is_symlink():
                    raise InvalidBundle("unexpected recovery symlink")
                if entry.is_dir(follow_symlinks=False):
                    if relative not in {"secrets", "embedding"}:
                        raise InvalidBundle("unexpected recovery directory")
                    visit(path)
                else:
                    if relative not in allowed:
                        raise InvalidBundle("unexpected recovery artifact")
                    _regular(path)
                    found.add(relative)

    visit(root)
    return found


def verify_bundle(root: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    expected = _sha(expected_manifest_sha256)
    if root.is_symlink() or not root.is_dir():
        raise InvalidBundle("recovery directory required")
    manifest_path = root / "manifest.json"
    size = _regular(manifest_path)
    if not 0 < size <= MAX_MANIFEST_BYTES or _digest(manifest_path, size) != expected:
        raise InvalidBundle("recovery inventory digest mismatch")
    # A second bounded read is checked against the independently retained digest,
    # so replacing the manifest between opens cannot change the verified input.
    with _open_checked(manifest_path, size) as stream:
        raw = stream.read(size + 1)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
        raise InvalidBundle("recovery manifest changed")
    try:
        item = validate_manifest(json.loads(raw, object_pairs_hook=_pairs))
    except InvalidBundle:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InvalidBundle("invalid recovery manifest") from exc
    if _inventory(root) != set(item["files"]) | {"manifest.json"}:
        raise InvalidBundle("unexpected or missing recovery artifact")
    for name, record in item["files"].items():
        path = root / name
        if _regular(path) != record["bytes"] or _digest(path, record["bytes"]) != record["sha256"]:
            raise InvalidBundle("recovery artifact digest mismatch")
    with _open_checked(root / "database.dump", item["files"]["database.dump"]["bytes"]) as stream:
        if stream.read(5) != b"PGDMP":
            raise InvalidBundle("custom PostgreSQL dump required")
    return item


def independent_destination(
    parent: Path, *, checkout: Path, database_volume: Path, secret_store: Path
) -> None:
    resolved = parent.resolve(strict=True)
    if parent != resolved or not resolved.is_dir():
        raise InvalidBundle("canonical backup storage directory required")
    backup_device = resolved.stat().st_dev
    for production in (checkout, database_volume, secret_store):
        actual = production.resolve(strict=True)
        if (
            resolved == actual
            or resolved.is_relative_to(actual)
            or backup_device == actual.stat().st_dev
        ):
            raise InvalidBundle("backup must use a separate filesystem from production")


def seal_bundle(
    destination: Path,
    sources: Mapping[str, Path],
    metadata: Mapping[str, Any],
) -> str:
    """Copy capture outputs into a new private directory; never overwrite.

    Caller must first verify independent_destination using actual daemon volume
    paths, and keep the returned digest in a different trusted inventory.
    Incomplete directories intentionally remain unsealed after errors.
    """
    if destination.exists() or destination.is_symlink():
        raise InvalidBundle("new recovery directory required")
    if not REQUIRED_FILES <= set(sources) or not set(sources) <= REQUIRED_FILES | OPTIONAL_FILES:
        raise InvalidBundle("incomplete recovery files")
    records: dict[str, ArtifactRecord] = {
        name: {"bytes": _regular(path), "sha256": _digest(path, _regular(path))}
        for name, path in sources.items()
    }
    manifest = validate_manifest({**metadata, "files": records})
    if (
        shutil.disk_usage(destination.parent).free
        < sum(r["bytes"] for r in records.values()) + 1024 * 1024
    ):
        raise InvalidBundle("insufficient backup storage")
    destination.mkdir(mode=0o700)
    for name, source in sources.items():
        target = destination / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (
            _open_checked(source, records[name]["bytes"]) as incoming,
            target.open("xb") as outgoing,
        ):
            os.chmod(target, 0o600)
            remaining = records[name]["bytes"]
            while remaining:
                chunk = incoming.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise InvalidBundle("capture changed while copying")
                outgoing.write(chunk)
                remaining -= len(chunk)
            if incoming.read(1):
                raise InvalidBundle("capture changed while copying")
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if _digest(target, records[name]["bytes"]) != records[name]["sha256"]:
            raise InvalidBundle("capture changed while copying")
    with _open_checked(destination / "database.dump", records["database.dump"]["bytes"]) as stream:
        if stream.read(5) != b"PGDMP":
            raise InvalidBundle("custom PostgreSQL dump required")
    for directory in (destination / "secrets", destination / "embedding"):
        if directory.exists():
            _sync_directory(directory)
    raw = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    temporary = destination / (".manifest-" + uuid4().hex)
    with temporary.open("xb") as stream:
        os.chmod(temporary, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.rename(destination / "manifest.json")
    _sync_directory(destination)
    _sync_directory(destination.parent)
    digest = hashlib.sha256(raw).hexdigest()
    verify_bundle(destination, digest)
    return digest
