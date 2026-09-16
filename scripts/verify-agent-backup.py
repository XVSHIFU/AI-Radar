"""Read-only bundle integrity check, not a database restore or release approval."""

import argparse
import json

from radar.recovery_bundle import InvalidBundle, verify_bundle


def main() -> None:
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        record = verify_bundle(args.directory, args.expected_manifest_sha256)
    except (OSError, InvalidBundle):
        raise SystemExit("backup_integrity_failed") from None
    print(
        json.dumps(
            {
                "status": "integrity_verified",
                "source_commit": record["source_commit"],
                "snapshot_at": record["snapshot"]["captured_at"],
                "schema": record["snapshot"]["schema"],
                "files": len(record["files"]),
                "database_restored": False,
            }
        )
    )


if __name__ == "__main__":
    main()
