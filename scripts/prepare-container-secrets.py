"""Create credentials for an EMPTY installation; never use during restore/cutover.

Operator-only Linux command. Existing HMAC values must instead be restored byte
for byte with the database, or IP quotas and anonymous ownership would change.
"""

from __future__ import annotations

import argparse
import os
import secrets
import stat
import sys
from pathlib import Path

NAMES = (
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


def create(directory: Path) -> None:
    if sys.platform != "linux" or os.getuid() != 0:
        raise ValueError("Linux operator root access required")
    if not directory.is_absolute() or directory.name in {"", ".", ".."}:
        raise ValueError("absolute new directory required")
    # Refuse symlink/writable ancestors and never overwrite an existing set.
    for parent in directory.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("root-owned non-writable parent directories required")
    directory.mkdir(mode=0o700)
    for name in NAMES:
        descriptor = os.open(
            directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_urlsafe(48).encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
            os.fchown(stream.fileno(), 10001, 10001)
            os.fchmod(stream.fileno(), 0o400)
    print(
        "created private credentials for a new empty installation; no values displayed"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-install", action="store_true", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        create(args.directory)
    except (OSError, ValueError):
        raise SystemExit(
            "secret_provision_failed; existing files were not overwritten"
        ) from None


if __name__ == "__main__":
    main()
