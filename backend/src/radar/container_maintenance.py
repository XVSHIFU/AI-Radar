"""Fixed maintenance supervisor; never reachable through model tool dispatch.

No automatic rerun after failure, timeout or provider halt. Successful batches
repeat at the existing maintenance cadence. SIGTERM cancels the current child
process group before releasing the deployment's inherited writer lock.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import TypeVar
from zoneinfo import ZoneInfo

INTERVALS = {"history-discover": 3600, "history-extract": 600, "embedding-index": 900}
DEADLINES = {"history-discover": 3600, "history-extract": 7200, "embedding-index": 900}


class MaintenanceHalted(RuntimeError):
    pass


def job_command(role: str, values: Mapping[str, str], today: date) -> list[str] | None:
    if role not in INTERVALS:
        raise ValueError("unsupported maintenance role")
    if role == "embedding-index":
        return [sys.executable, "-m", "radar.embedding_indexer", "--limit", "100"]
    start = date.fromisoformat(values["RADAR_HISTORY_FROM"])
    last = date.fromisoformat(values["RADAR_HISTORY_TO"])
    if start > last:
        raise ValueError("invalid maintenance date window")
    end = min(today, last)
    if start > end:
        return None
    module = "radar.backfill" if role == "history-discover" else "radar.extract_events"
    result = [
        sys.executable,
        "-m",
        module,
        "--date-from",
        start.isoformat(),
        "--date-to",
        end.isoformat(),
    ]
    if role == "history-extract":
        result += ["--limit", "80"]
    else:
        result += ["--max-pages", "40"]
    return result


T = TypeVar("T")


async def settled[T](task: asyncio.Task[T]) -> tuple[T, bool]:
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            interrupted = True
    return task.result(), interrupted


async def terminate(process: asyncio.subprocess.Process) -> None:
    # Children are created in a dedicated group in this container's PID namespace.
    # Clean remaining descendants even if the direct child has already exited.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        async with asyncio.timeout(5):
            await process.wait()
    except TimeoutError:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    await process.wait()


async def execute(args: list[str], stop: asyncio.Event, deadline: float) -> int | None:
    if stop.is_set():
        return None
    spawning = asyncio.create_task(asyncio.create_subprocess_exec(*args, start_new_session=True))
    try:
        process = await asyncio.shield(spawning)
    except asyncio.CancelledError:
        process, _ = await settled(spawning)
        await settled(asyncio.create_task(terminate(process)))
        raise
    finished = asyncio.create_task(process.wait())
    stopping = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait(
            {finished, stopping}, timeout=deadline, return_when=asyncio.FIRST_COMPLETED
        )
        if finished in done:
            return finished.result()
        if stopping in done:
            return None
        raise MaintenanceHalted("maintenance_deadline_exceeded")
    finally:
        cleanup = asyncio.create_task(terminate(process))
        try:
            _, interrupted = await settled(cleanup)
        finally:
            stopping.cancel()
            await asyncio.gather(stopping, return_exceptions=True)
            await asyncio.gather(finished, return_exceptions=True)
        if interrupted:
            raise asyncio.CancelledError


async def supervise(
    role: str,
    values: Mapping[str, str],
    stop: asyncio.Event,
    *,
    today: Callable[[], date] | None = None,
) -> None:
    if role not in INTERVALS:
        raise ValueError("unsupported maintenance role")
    zone = ZoneInfo(values.get("BUSINESS_TIMEZONE", "Asia/Shanghai"))
    clock = today or (lambda: datetime.now(zone).date())
    while not stop.is_set():
        args = job_command(role, values, clock())
        if args is not None:
            status = await execute(args, stop, DEADLINES[role])
            if status not in (None, 0):
                raise MaintenanceHalted("maintenance_batch_stopped")
        if stop.is_set():
            return
        try:
            async with asyncio.timeout(INTERVALS[role]):
                await stop.wait()
        except TimeoutError:
            continue


async def run(role: str) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    try:
        await supervise(role, os.environ, stop)
    finally:
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(signum)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=sorted(INTERVALS))
    args = parser.parse_args()
    try:
        asyncio.run(run(args.role))
    except (MaintenanceHalted, OSError, ValueError, KeyError):
        # Neither connection parameters nor model error bodies belong here.
        raise SystemExit("maintenance_stopped; operator review required") from None


if __name__ == "__main__":
    main()
