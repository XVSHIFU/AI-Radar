import hashlib
import json

import pytest

from radar.recovery_bundle import (
    FINGERPRINT_TABLES,
    REQUIRED_FILES,
    InvalidBundle,
    independent_destination,
    seal_bundle,
    verify_bundle,
)


def capture(tmp_path):
    source = tmp_path / "capture"
    source.mkdir()
    paths = {}
    for name in REQUIRED_FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        # Synthetic test artifacts are NOT restorable PostgreSQL / Docker files.
        body = b"PGDMPsynthetic" if name == "database.dump" else ("fixture:" + name).encode()
        if name.startswith("secrets/"):
            body = b" preserve-the-existing-value-byte-for-byte "
        path.write_bytes(body)
        paths[name] = path
    metadata = {
        "format": "ai-radar-recovery/1",
        "created_at": "2026-09-16T09:00:01Z",
        "source_commit": "a" * 40,
        "images": {name: "sha256:" + "b" * 64 for name in ["backend", "db", "pi", "gateway"]},
        "snapshot": {
            "schema": "0013",
            "captured_at": "2026-09-16T09:00:00Z",
            "snapshot_id": "00000001-00000002-1",
            "fingerprints": {name: {"rows": 20, "sha256": "c" * 64} for name in FINGERPRINT_TABLES},
        },
    }
    return paths, metadata


def sealed(tmp_path):
    paths, metadata = capture(tmp_path)
    output = tmp_path / "new-backup"
    digest = seal_bundle(output, paths, metadata)
    return output, digest


def test_bundle_preserves_identity_bytes_and_snapshot_fingerprints(tmp_path):
    output, digest = sealed(tmp_path)
    value = verify_bundle(output, digest)
    assert value["snapshot"]["fingerprints"]["public_ask_requests"]["rows"] == 20
    assert (
        output / "secrets/public_assistant_secret"
    ).read_bytes() == b" preserve-the-existing-value-byte-for-byte "
    assert value["source_commit"] == "a" * 40


@pytest.mark.parametrize("name", ["database.dump", "secrets/public_assistant_secret", "images.tar"])
def test_tampering_with_same_length_artifact_is_detected(tmp_path, name):
    output, digest = sealed(tmp_path)
    path = output / name
    original = path.read_bytes()
    path.write_bytes(b"!" + original[1:])
    with pytest.raises(InvalidBundle, match="digest"):
        verify_bundle(output, digest)


def test_manifest_must_match_a_separately_retained_digest(tmp_path):
    output, digest = sealed(tmp_path)
    record = json.loads((output / "manifest.json").read_text())
    record["snapshot"]["fingerprints"]["public_ask_requests"]["rows"] = 0
    (output / "manifest.json").write_text(json.dumps(record))
    with pytest.raises(InvalidBundle, match="inventory digest"):
        verify_bundle(output, digest)


def test_unexpected_and_missing_files_are_rejected(tmp_path):
    output, digest = sealed(tmp_path)
    extra = output / "unexpected"
    extra.write_text("not allowed")
    with pytest.raises(InvalidBundle, match="unexpected"):
        verify_bundle(output, digest)
    extra.unlink()
    (output / "secrets/public_assistant_secret").unlink()
    with pytest.raises(InvalidBundle, match="missing"):
        verify_bundle(output, digest)


def test_existing_destination_is_never_overwritten(tmp_path):
    paths, metadata = capture(tmp_path)
    destination = tmp_path / "live"
    destination.mkdir()
    sentinel = destination / "data"
    sentinel.write_text("live")
    with pytest.raises(InvalidBundle, match="new recovery"):
        seal_bundle(destination, paths, metadata)
    assert sentinel.read_text() == "live"


def test_path_traversal_is_rejected_before_any_destination_write(tmp_path):
    paths, metadata = capture(tmp_path)
    paths["../escape"] = tmp_path / "does-not-exist"
    with pytest.raises(InvalidBundle, match="incomplete"):
        seal_bundle(tmp_path / "new", paths, metadata)
    assert not (tmp_path / "new").exists()
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("change", ["ledger", "boolean", "timestamp", "image", "schema"])
def test_incomplete_or_ambiguous_snapshot_metadata_is_rejected(tmp_path, change):
    paths, metadata = capture(tmp_path)
    if change == "ledger":
        del metadata["snapshot"]["fingerprints"]["research_model_calls"]
    elif change == "boolean":
        metadata["snapshot"]["fingerprints"]["public_ask_requests"]["rows"] = True
    elif change == "timestamp":
        metadata["snapshot"]["captured_at"] = "2026-09-16T10:00:00Z"
    elif change == "image":
        metadata["images"]["backend"] = "image:latest"
    else:
        metadata["snapshot"]["schema"] = "0011"
    with pytest.raises(InvalidBundle):
        seal_bundle(tmp_path / "new", paths, metadata)
    assert not (tmp_path / "new").exists()


def test_truncated_custom_dump_is_not_sealed(tmp_path):
    paths, metadata = capture(tmp_path)
    paths["database.dump"].write_bytes(b"PG")
    with pytest.raises(InvalidBundle, match="custom PostgreSQL"):
        seal_bundle(tmp_path / "new", paths, metadata)
    assert not (tmp_path / "new/manifest.json").exists()


def test_duplicate_json_keys_are_rejected_even_with_a_matching_file_digest(tmp_path):
    output, _ = sealed(tmp_path)
    raw = (output / "manifest.json").read_bytes()
    raw = b'{"format":"invalid",' + raw[1:]
    (output / "manifest.json").write_bytes(raw)
    with pytest.raises(InvalidBundle, match="duplicate"):
        verify_bundle(output, hashlib.sha256(raw).hexdigest())


def test_backup_on_same_filesystem_is_not_called_independent(tmp_path):
    backup = tmp_path / "backup"
    backup.mkdir()
    with pytest.raises(InvalidBundle, match="separate filesystem"):
        independent_destination(
            backup.resolve(), checkout=tmp_path, database_volume=tmp_path, secret_store=tmp_path
        )


def test_embedding_image_requires_both_model_artifacts(tmp_path):
    paths, metadata = capture(tmp_path)
    metadata["images"]["embedding"] = "sha256:" + "d" * 64
    with pytest.raises(InvalidBundle, match="captured together"):
        seal_bundle(tmp_path / "new", paths, metadata)
