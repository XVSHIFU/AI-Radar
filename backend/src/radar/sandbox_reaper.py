"""Independent watchdog for expired, explicitly owned sandbox containers.

Run separately from the request controller (e.g. a five-second systemd timer).
No provider configuration, API credentials or business database is loaded.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from .research_guard import ResearchRejected
from .research_stream import strict_json
from .sandbox_executor import Commands, DockerCommands

MAX_AGE = timedelta(seconds=30)
NAME = re.compile(r"/radar-python-[a-f0-9]{32}\Z")
CONTAINER_ID = re.compile(r"[a-f0-9]{12,64}\Z")


def expired_owned(container: Any, now: datetime) -> bool:
    try:
        if not isinstance(container, dict):
            raise ValueError("invalid container")
        labels = container["Config"].get("Labels") or {}
        if labels.get("ai-radar.sandbox") != "task" or not NAME.fullmatch(container["Name"]):
            return False
        host = container["HostConfig"]
        if (
            host["Runtime"] != "runsc"
            or host["NetworkMode"] != "none"
            or host["Privileged"] is not False
            or host["ReadonlyRootfs"] is not True
            or container["Config"]["User"] != "65532:65532"
        ):
            raise ValueError("unexpected sandbox configuration")
        created = datetime.fromisoformat(container["Created"])
        if created.tzinfo is None or now.tzinfo is None:
            raise ValueError("timezone required")
        return created <= now - MAX_AGE
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ResearchRejected("SANDBOX_WATCHDOG_FAILED") from exc


async def reap_expired(commands: Commands, *, now: datetime | None = None) -> dict[str, int]:
    checked_at = now or datetime.now(UTC)
    listed = await commands.execute(
        ["ps", "--all", "--filter", "label=ai-radar.sandbox=task", "--format", "{{.ID}}"]
    )
    ids = listed.stdout.decode("ascii").split()
    if listed.code or len(ids) > 128 or any(not CONTAINER_ID.fullmatch(i) for i in ids):
        raise ResearchRejected("SANDBOX_WATCHDOG_FAILED")
    removed, checked = 0, 0
    for container_id in ids:
        inspected = await commands.execute(["inspect", container_id])
        if inspected.code:
            # A request may have removed the object between list and inspect.
            absent = await commands.execute(
                ["ps", "--all", "--filter", "id=" + container_id, "--format", "{{.ID}}"]
            )
            if absent.code or absent.stdout.strip():
                raise ResearchRejected("SANDBOX_WATCHDOG_FAILED")
            continue
        try:
            data = strict_json(inspected.stdout.decode())
            if not isinstance(data, list) or len(data) != 1:
                raise ValueError("container inspect shape")
            owned = expired_owned(data[0], checked_at)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ResearchRejected("SANDBOX_WATCHDOG_FAILED") from exc
        checked += 1
        if owned:
            result = await commands.execute(["rm", "--force", "--volumes", container_id])
            if result.code:
                absent = await commands.execute(
                    ["ps", "--all", "--filter", "id=" + container_id, "--format", "{{.ID}}"]
                )
                if absent.code or absent.stdout.strip():
                    raise ResearchRejected("SANDBOX_WATCHDOG_FAILED")
            removed += 1
    return {"checked": checked, "removed": removed}


def main() -> None:
    try:
        # Bound a whole sweep as well as individual Docker commands.
        result = asyncio.run(asyncio.wait_for(reap_expired(DockerCommands()), timeout=20))
    except (ResearchRejected, OSError, TimeoutError, UnicodeError):
        print('{"status":"failed","code":"SANDBOX_WATCHDOG_FAILED"}')
        raise SystemExit(1) from None
    print(json.dumps({"status": "completed", **result}))


if __name__ == "__main__":
    main()
