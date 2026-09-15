"""Runs only INSIDE a per-task sandbox. This interpreter is not a security boundary.

No deployment configuration is imported. The external controller must enforce
gVisor, network=none, readonly rootfs, memory/PID/CPU limits and forced termination.
"""

import base64
import contextlib
import io
import json
import os
import re
import stat
import sys
from pathlib import Path

OUTPUT_LIMIT = 1048576
STDOUT_LIMIT = 65536


class LimitedOutput(io.TextIOBase):
    def __init__(self):
        self.parts = []
        self.size = 0

    def write(self, value):
        size = len(value.encode("utf-8"))
        if self.size + size > STDOUT_LIMIT:
            raise ValueError("STDOUT_LIMIT")
        self.size += size
        self.parts.append(value)
        return len(value)


def run():
    # Deployment guard against an accidental developer invocation. It is not a
    # protection against generated code, which must be treated as arbitrary code.
    if not os.path.isfile("/.dockerenv") or os.getuid() == 0:
        raise RuntimeError("PER_TASK_SANDBOX_REQUIRED")
    raw = sys.stdin.buffer.read(2228225)
    if len(raw) > 2228224:
        raise ValueError("INPUT_LIMIT")
    task = json.loads(raw)
    if set(task) != {"code", "datasets"} or len(task["code"].encode()) > 16384:
        raise ValueError("INVALID_INPUT")
    output = Path("/tmp/output")
    output.mkdir(mode=0o700, exist_ok=False)
    capture = LimitedOutput()
    namespace = {"__name__": "__analysis__", "datasets": task["datasets"], "output_dir": str(output)}
    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
        exec(compile(task["code"], "<analysis>", "exec"), namespace)
    artifacts, size = [], 0
    for path in sorted(output.iterdir()):
        if len(artifacts) >= 8:
            raise ValueError("INVALID_ARTIFACT")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,59}\.(json|csv|png)", path.name):
            raise ValueError("INVALID_ARTIFACT")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as artifact:
            info = os.fstat(artifact.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("INVALID_ARTIFACT")
            if info.st_size > OUTPUT_LIMIT - size:
                raise ValueError("OUTPUT_LIMIT")
            data = artifact.read(OUTPUT_LIMIT - size + 1)
        size += len(data)
        if size > OUTPUT_LIMIT:
            raise ValueError("OUTPUT_LIMIT")
        artifacts.append({"name": path.name, "data": base64.b64encode(data).decode("ascii")})
    return {"status": "completed", "stdout": "".join(capture.parts), "artifacts": artifacts}


if __name__ == "__main__":
    try:
        result = run()
    except BaseException:
        result = {"status": "failed", "code": "EXECUTION_FAILED"}
    # Generated code may tamper with the worker. The external controller validates
    # this entire byte stream independently and never trusts a self-reported success.
    sys.__stdout__.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
