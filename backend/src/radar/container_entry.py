"""Fixed operator entry points for the separated Compose deployment.

Not a model tool. Secret files are mounted individually per service; no arbitrary
commands, config paths or provider tokens are accepted from request data.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import stat
import sys
from collections.abc import Mapping
from pathlib import Path

DB_USERS = {
    "api": "radar_api",
    "worker": "radar_ingest",
    "scheduler": "radar_ingest",
    "quota-cleaner": "radar_api",
    "migrate": "radar_owner",
    "register-sources": "radar_ingest",
    "history-discover": "radar_ingest",
    "history-extract": "radar_ingest",
    "embedding-index": "radar_ingest",
    "embedding-activate": "radar_ingest",
}
API_SECRETS = {
    "ADMIN_TOKEN": "admin_token",
    "CURSOR_SECRET": "cursor_secret",
    "PUBLIC_ASSISTANT_SECRET": "public_assistant_secret",
    "RESEARCH_RUNTIME_TOKEN": "runtime_token",
    "SANDBOX_CONTROLLER_TOKEN": "sandbox_token",
}


def private_value(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or not 1 <= info.st_size <= 4096
        ):
            raise ValueError("private service credential required")
        raw = stream.read(4097)
    # Preserve an existing signing secret exactly. Provisioners write no newline;
    # do not strip spaces or silently regenerate identity / quota HMAC material.
    value = raw.decode("utf-8")
    if len(raw) > 4096 or not value or any(ord(char) < 32 for char in value):
        raise ValueError("invalid private service credential")
    return value


def environment(role: str, inherited: Mapping[str, str]) -> dict[str, str]:
    if role not in DB_USERS:
        raise ValueError("unsupported container role")
    # Explicit non-secret configuration only; neither DATABASE_URL nor a host
    # .env may override service identity. No credentials on the command line.
    allowed = {
        "PATH",
        "LANG",
        "TZ",
        "PYTHONPATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONUNBUFFERED",
        "HOME",
        "FETCH_INTERVAL_SECONDS",
        "FETCH_DNS_MODE",
        "BUSINESS_TIMEZONE",
        "RESEARCH_AGENT_ENABLED",
        "SANDBOX_IMAGE_ID",
        "ASSISTANT_INPUT_PER_DAY",
        "ASSISTANT_OUTPUT_PER_DAY",
    }
    result = {key: value for key, value in inherited.items() if key in allowed}
    result.update(
        {
            "RADAR_DATA_MODE": "postgres",
            "DB_HOST": "db",
            "DB_PORT": "5432",
            "DB_NAME": "ai_radar",
            "DB_USER": DB_USERS[role],
            "DB_PASSWORD": private_value(Path("/run/secrets/db_password")),
            "MODEL_CONFIG_PATH": "/var/lib/radar-model/model.json",
        }
    )
    if role == "api":
        result.update(
            {name: private_value(Path("/run/secrets") / file) for name, file in API_SECRETS.items()}
        )
        result["RESEARCH_RUNTIME_URL"] = "http://pi-runtime:8081"
        result["SANDBOX_CONTROLLER_URL"] = "http://sandbox-controller:8092"
    else:
        result["RESEARCH_AGENT_ENABLED"] = "false"
    if role in {"history-discover", "history-extract"}:
        for key in ("RADAR_HISTORY_FROM", "RADAR_HISTORY_TO"):
            result[key] = inherited[key]
    if role in {"embedding-index", "embedding-activate"} or (
        role == "api" and inherited.get("EMBEDDING_MODEL_DIR")
    ):
        from .container_model import MODEL_ROOT, REVISION

        if inherited.get("EMBEDDING_MODEL_DIR") != str(MODEL_ROOT):
            raise ValueError("fixed embedding mount required")
        if inherited.get("EMBEDDING_MODEL_REVISION") != REVISION:
            raise ValueError("verified embedding revision required")
        result["EMBEDDING_MODEL_DIR"] = str(MODEL_ROOT)
        result["EMBEDDING_MODEL_REVISION"] = REVISION
        result["EMBEDDING_THREADS"] = "4"
    return result


def command(role: str) -> list[str]:
    commands = {
        "api": [
            sys.executable,
            "-m",
            "uvicorn",
            "radar.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--workers",
            "1",
            "--proxy-headers",
            "--forwarded-allow-ips",
            "172.30.248.2",
            "--no-access-log",
        ],
        "worker": [sys.executable, "-m", "app.worker"],
        "scheduler": [sys.executable, "-m", "app.scheduler"],
        "migrate": [sys.executable, "-m", "alembic", "upgrade", "head"],
        "register-sources": [sys.executable, "-m", "radar.register_sources"],
    }
    if role in {"history-discover", "history-extract", "embedding-index"}:
        return [sys.executable, "-m", "radar.container_maintenance", role]
    if role == "embedding-activate":
        return [sys.executable, "-m", "radar.embedding_indexer", "--limit", "500", "--activate"]
    if role not in commands:
        raise ValueError("unsupported container command")
    return commands[role]


async def quota_loop() -> None:
    from .public_quota_cleanup import main as clean

    # The existing maintenance entry does its own safe error reporting and
    # transaction rollback. Stop on failure rather than silently losing cleanup.
    while True:
        await asyncio.to_thread(clean)
        await asyncio.sleep(300)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=sorted(DB_USERS))
    role = parser.parse_args().role
    try:
        values = environment(role, os.environ)
    except (OSError, ValueError, UnicodeError, KeyError):
        raise SystemExit("container_credentials_invalid") from None
    os.environ.clear()
    os.environ.update(values)
    os.umask(0o077)
    os.chdir("/app/backend")
    # Same-host stack slots must share this external volume. Restored databases
    # on another host still require deployment-level fencing before promotion.
    if role != "register-sources":
        from .service_lock import acquire_lock

        lock_name = "embedding-index" if role == "embedding-activate" else role
        lock = acquire_lock(Path("/run/radar-service-locks") / (lock_name + ".lock"))
        os.set_inheritable(lock.fileno(), True)
    if values.get("EMBEDDING_MODEL_DIR"):
        from .container_model import verify_model

        try:
            verify_model()
        except (OSError, ValueError):
            raise SystemExit("embedding_model_unverified") from None
    if role == "quota-cleaner":
        asyncio.run(quota_loop())
    else:
        args = command(role)
        os.execve(args[0], args, values)


if __name__ == "__main__":
    main()
