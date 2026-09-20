"""Regression check for release settings retained after a snapshot restore."""

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RELEASE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "release.py"
SPEC = importlib.util.spec_from_file_location("release", RELEASE_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class RestoreOptionsTest(unittest.TestCase):
    def test_restore_persists_new_stack_and_network(self) -> None:
        old = {
            "RADAR_STACK": "original",
            "RADAR_HTTP_PORT": "8080",
            "RADAR_FRONT_SUBNET": "172.31.249.0/29",
            "RADAR_GATEWAY_IP": "172.31.249.2",
            "RADAR_API_IP": "172.31.249.3",
        }
        new = {
            "RADAR_STACK": "restored",
            "RADAR_HTTP_PORT": "8081",
            "RADAR_FRONT_SUBNET": "172.31.250.0/29",
            "RADAR_GATEWAY_IP": "172.31.250.2",
            "RADAR_API_IP": "172.31.250.3",
        }
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            snapshot = base / "snapshot"
            snapshot.mkdir()
            target = base / "restored"
            dump = b"test dump"
            (snapshot / "database.dump").write_bytes(dump)
            archive_path = snapshot / "configuration.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                for name in release.SECRET_NAMES:
                    content = b"test-secret"
                    member = tarfile.TarInfo("secrets/" + name)
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
                options = json.dumps(old).encode()
                member = tarfile.TarInfo("release-options.json")
                member.size = len(options)
                archive.addfile(member, io.BytesIO(options))
            files = {
                name: {
                    "bytes": (snapshot / name).stat().st_size,
                    "sha256": hashlib.sha256((snapshot / name).read_bytes()).hexdigest(),
                }
                for name in ("database.dump", "configuration.tar.gz")
            }
            (snapshot / "manifest.json").write_text(
                json.dumps({"format": 1, "release": release.VERSION, "files": files})
            )

            def fake_compose(_root, *args, **_kwargs):
                output = b"" if "--list" not in args else b"; empty test archive\n"
                return subprocess.CompletedProcess(args, 0, stdout=output)

            with patch.dict(os.environ, new), patch.object(
                release.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=b""),
            ), patch.object(release, "set_container_ownership"), patch.object(
                release, "compose", side_effect=fake_compose
            ):
                release.restore(target, snapshot)

            self.assertEqual({key: release.selected(target)[key] for key in new}, new)


if __name__ == "__main__":
    unittest.main()
