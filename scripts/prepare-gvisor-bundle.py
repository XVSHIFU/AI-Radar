"""Download and verify one pinned official runtime bundle; never install it.

Run on the sandbox Ubuntu host with Python 3.12+. Output directory must be new.
No Docker operations, sudo, service restarts or downloaded program execution.
"""

import argparse
import hashlib
import json
import os
import re
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

VERSION = "20260907.0"
BASE = f"https://storage.googleapis.com/gvisor/releases/release/{VERSION}/x86_64"


def fetch(url, destination, maximum):
    request = urllib.request.Request(
        url, headers={"User-Agent": "ai-radar-runtime-preparation/1"}
    )
    size = 0
    with (
        urllib.request.urlopen(request, timeout=30) as response,
        destination.open("xb") as output,
    ):
        if response.url != url:
            raise ValueError("unexpected download redirect")
        while block := response.read(1024 * 1024):
            size += len(block)
            if size > maximum:
                raise ValueError("download size limit")
            output.write(block)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "posix" or os.uname().machine != "x86_64":
        raise SystemExit("This pinned bundle is for Linux x86_64 only.")
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    archive = output / "gvisor.tar.bz2"
    checksum = output / "gvisor.tar.bz2.sha512"
    fetch(BASE + "/gvisor.tar.bz2.sha512", checksum, 4096)
    fields = checksum.read_text(encoding="ascii").strip().split()
    if len(fields) != 2 or not re.fullmatch(r"[a-f0-9]{128}", fields[0]):
        raise ValueError("invalid official checksum")
    if fields[1].lstrip("*") != "gvisor.tar.bz2":
        raise ValueError("unexpected checksum filename")
    fetch(BASE + "/gvisor.tar.bz2", archive, 200 * 1024 * 1024)
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha512").hexdigest()
    if digest != fields[0]:
        raise ValueError("official checksum mismatch")
    names, size, files = set(), 0, []
    with tarfile.open(archive, "r:bz2") as bundle:
        for item in bundle:
            path = PurePosixPath(item.name)
            if item.name in {".", "./"} and item.isdir():
                continue
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("invalid archive path")
            if path.parts[0] not in {"runsc", "containerd-shim-runsc-v1", "gvisor-bin"}:
                raise ValueError("unexpected archive entry")
            if not (item.isfile() or item.isdir()) or item.mode & 0o7000:
                raise ValueError("unsafe archive type or mode")
            if str(path) in names or len(names) > 1000:
                raise ValueError("duplicate or oversized archive")
            names.add(str(path))
            size += item.size
            if size > 512 * 1024 * 1024:
                raise ValueError("unpacked size limit")
            if item.isfile():
                source = bundle.extractfile(item)
                if source is None:
                    raise ValueError("missing archive file")
                with source:
                    files.append(
                        {
                            "path": str(path),
                            "size": item.size,
                            "sha256": hashlib.file_digest(source, "sha256").hexdigest(),
                        }
                    )
    if not {"runsc", "containerd-shim-runsc-v1"}.issubset({f["path"] for f in files}):
        raise ValueError("incomplete runtime bundle")
    report = {
        "version": VERSION,
        "architecture": "x86_64",
        "source": BASE,
        "archive_sha512": digest,
        "files": files,
        "status": "verified_download_only_not_installed",
    }
    (output / "manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": report["status"], "version": VERSION, "file_count": len(files)}
        )
    )


if __name__ == "__main__":
    main()
