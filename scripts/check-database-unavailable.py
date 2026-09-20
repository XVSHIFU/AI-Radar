"""Verify that an unavailable PostgreSQL server prevents application startup."""

import errno
import json
import os
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def refused_connection(error: Exception) -> str | None:
    """Recognize only connection refusal in the startup exception chain."""
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ConnectionRefusedError) or (
            isinstance(current, OSError)
            and current.errno in {errno.ECONNREFUSED, 10061, 1225}
        ):
            return type(current).__name__
        pending.extend(
            item
            for item in (current.__cause__, current.__context__, getattr(current, "orig", None))
            if isinstance(item, BaseException)
        )
    return None


def main() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        os.environ["RADAR_DATA_MODE"] = "postgres"
        os.environ["DATABASE_URL"] = (
            f"postgresql+asyncpg://synthetic@127.0.0.1:{port}/synthetic"
        )
        os.environ["ADMIN_TOKEN"] = "synthetic-local-test"
        from fastapi.testclient import TestClient

        from radar.config import get_settings
        from radar.main import app

        get_settings.cache_clear()
        startup_rejected = False
        reason = None
        try:
            with TestClient(app, raise_server_exceptions=False):
                pass
        except Exception as exc:
            startup_rejected = True
            reason = refused_connection(exc)
        finally:
            get_settings.cache_clear()

    passed = startup_rejected and reason is not None
    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "layer": "real_loopback_connection_refused_startup_fail_closed",
        "postgres_integration_executed": False,
        "passed": int(passed),
        "total": 1,
        "checks": [
            {
                "check": "startup_denied_on_connection_refusal",
                "startup_rejected": startup_rejected,
                "cause": reason,
                "passed": passed,
            }
        ],
    }
    (ROOT / "docs/database-unavailable-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": report["passed"], "total": report["total"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
