"""Prove independent cleanup after killing a dedicated test controller.

Use only during sandbox acceptance, before public Python is enabled. Runs a fixed
sleep task with synthetic data. Never kills the API or another task's controller.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from radar.sandbox_executor import DockerCommands, SandboxExecutor

CHILD = """import asyncio, json, sys
from radar.sandbox_executor import DockerCommands, SandboxExecutor
class Observe(DockerCommands):
    async def execute(self, arguments, **kwargs):
        value = await super().execute(arguments, **kwargs)
        if arguments[0] == 'create' and value.code == 0:
            print(json.dumps({'name': arguments[2]}), flush=True)
        return value
asyncio.run(SandboxExecutor(Observe(), sys.argv[1]).run(
    'import time; time.sleep(60)', [{'rows':[{'count':1}]}]))
"""


async def verify(image):
    commands = DockerCommands()
    SandboxExecutor(
        commands, image
    )  # Validate the immutable image reference before starting.
    timer = await asyncio.create_subprocess_exec(
        "systemctl",
        "--user",
        "is-active",
        "ai-radar-sandbox-watchdog.timer",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert await asyncio.wait_for(timer.wait(), timeout=5) == 0, (
        "watchdog timer is inactive"
    )
    root = Path(__file__).resolve().parents[1]
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        CHILD,
        image,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(root / "backend/src")},
        limit=1024,
    )
    name = None
    start = time.monotonic()
    try:
        assert child.stdout is not None
        raw = await asyncio.wait_for(child.stdout.readline(), timeout=6)
        record = json.loads(raw)
        assert isinstance(record, dict) and set(record) == {"name"}
        candidate = record["name"]
        assert isinstance(candidate, str) and re.fullmatch(
            r"radar-python-[0-9a-f]{32}", candidate
        )
        name = candidate
        async with asyncio.timeout(6):
            while True:
                inspected = await commands.execute(["inspect", name])
                assert inspected.code == 0
                container = json.loads(inspected.stdout)[0]
                if container["State"]["Running"]:
                    break
                await asyncio.sleep(0.1)
        child.kill()
        assert await asyncio.wait_for(child.wait(), timeout=3) == -9
        print('{"phase":"test_controller_killed","container_running":true}', flush=True)
        async with asyncio.timeout(45):
            while True:
                checked = await commands.execute(
                    [
                        "ps",
                        "--all",
                        "--filter",
                        "name=^/" + name + "$",
                        "--format",
                        "{{.ID}}",
                    ]
                )
                assert checked.code == 0
                if not checked.stdout.strip():
                    break
                await asyncio.sleep(1)
        elapsed = round(time.monotonic() - start, 2)
        assert 29 <= elapsed <= 42
        return {
            "status": "passed",
            "controller_exit": child.returncode,
            "removed_by_independent_watchdog": True,
            "duration_seconds": elapsed,
            "python_enabled": False,
        }
    finally:
        if child.returncode is None:
            child.kill()
            await asyncio.wait_for(child.wait(), timeout=3)
        if name:
            remaining = await commands.execute(
                [
                    "ps",
                    "--all",
                    "--filter",
                    "name=^/" + name + "$",
                    "--format",
                    "{{.ID}}",
                ]
            )
            if remaining.stdout.strip():
                # A cleanup fallback only; the failed test cannot count as a pass.
                await commands.execute(["rm", "--force", "--volumes", name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    descriptor = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write('{"status":"started"}')
        output.flush()
        try:
            result = asyncio.run(verify(args.image))
        except (
            AssertionError,
            OSError,
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
        ) as exc:
            result = {"status": "failed", "code": type(exc).__name__}
        output.seek(0)
        json.dump(result, output, indent=2)
        output.truncate()
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps(result), flush=True)
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
