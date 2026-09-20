"""Save one PostgreSQL database dump on this machine."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

from release import compose, data_root, require_linux


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require_linux()
    root = data_root(args.data_root)
    target = args.output.expanduser().absolute()
    if target.is_symlink() or target.is_dir():
        parser.error("--output must be a regular database dump file")
    if target.resolve().is_relative_to(root.resolve()):
        parser.error("Keep the backup outside the live data directory")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".database-", delete=False) as stream:
            temporary = Path(stream.name)
            compose(root, "exec", "-T", "db", "pg_dump", "-U", "radar_bootstrap",
                    "-d", "ai_radar", "-Fc", "--no-owner", "--no-acl", stdout=stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Database backup saved to {target}")


if __name__ == "__main__":
    main()
