"""Operator acceptance tests: fixed programs run only in the pinned gVisor sandbox.

No provider calls or business data. Requires the candidate backend on PYTHONPATH.
Writes a new report; never enables Python or changes daemon configuration.
"""

import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

from radar.research_guard import ResearchRejected
from radar.sandbox_executor import DockerCommands, SandboxExecutor

RUNTIME = Path("/opt/ai-radar/gvisor/20260907.0/runsc")
RUNTIME_HASH = "3e0df2fa28f6ff5430b004f92573b81b75f442f78c780e0c85fdf6c2d572817a"
DATA = [
    {
        "rows": [
            {"category": "research", "count": 2},
            {"category": "product", "count": 3},
        ]
    }
]


class ObservedCommands(DockerCommands):
    def __init__(self):
        self.names = []
        self.starting = asyncio.Event()
        self.configurations_checked = 0

    async def execute(self, arguments, **kwargs):
        result = await super().execute(arguments, **kwargs)
        if arguments[0] == "create" and result.code == 0:
            self.names.append(arguments[2])
            inspected = await super().execute(["inspect", arguments[2]])
            container = json.loads(inspected.stdout)[0]
            host = container["HostConfig"]
            assert host["Runtime"] == "runsc" and host["NetworkMode"] == "none"
            assert host["ReadonlyRootfs"] and not host["Privileged"]
            assert not host.get("Binds") and not host.get("VolumesFrom")
            assert not host.get("Devices") and not host.get("PortBindings")
            assert host["Memory"] == host["MemorySwap"] == 268435456
            assert host["NanoCpus"] == 1000000000 and host["PidsLimit"] == 32
            limits = {
                item["Name"]: (item["Soft"], item["Hard"]) for item in host["Ulimits"]
            }
            assert limits["nproc"] == (2, 2)
            assert host["CapDrop"] == ["ALL"] and not host.get("CapAdd")
            assert "no-new-privileges:true" in host["SecurityOpt"]
            assert host["LogConfig"]["Type"] == "none"
            assert container["Config"]["User"] == "65532:65532"
            assert all(
                m["Type"] == "tmpfs" and m["Destination"] == "/tmp"
                for m in container["Mounts"]
            )
            self.configurations_checked += 1
            self.starting.set()
        return result

    async def assert_removed(self):
        for name in self.names:
            checked = await super().execute(
                [
                    "ps",
                    "--all",
                    "--filter",
                    "name=^/" + name + "$",
                    "--format",
                    "{{.ID}}",
                ]
            )
            assert checked.code == 0 and not checked.stdout.strip(), (
                "task container remains"
            )


CASES = [
    (
        "analysis_and_artifacts",
        """
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
frame = pd.DataFrame(datasets[0]['rows'])
result = {'sum': int(np.sum(frame['count'])), 'mean': float(np.mean(frame['count']))}
Path(output_dir, 'summary.json').write_text(json.dumps(result))
frame.to_csv(Path(output_dir, 'counts.csv'), index=False)
fig, ax = plt.subplots(figsize=(3, 2))
ax.bar(frame['category'], frame['count'])
fig.savefig(Path(output_dir, 'plot.png'))
print('analysis-ok')
""",
        None,
    ),
    (
        "permissions_and_host_access",
        """
import os, importlib.util
from pathlib import Path
assert os.getuid() == 65532
for name in ('/home/xvsf/ai-radar/.env', '/run/docker.sock', '/var/run/docker.sock',
             '/proc/1/root/home/xvsf/ai-radar/.env', '/home/xvsf/.ssh/id_ed25519'):
    assert not Path(name).exists(), 'host resource visible'
assert not any('API_KEY' in key or 'DATABASE_URL' in key or 'TOKEN' in key for key in os.environ)
assert importlib.util.find_spec('pip') is None
assert importlib.util.find_spec('ensurepip') is None
try:
    Path('/opt/forbidden').write_text('test')
except OSError:
    pass
else:
    raise AssertionError('root filesystem writable')
try:
    os.setuid(0)
except PermissionError:
    pass
else:
    raise AssertionError('privilege escalation')
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert int(status['CapEff'].strip(), 16) == 0
assert status['NoNewPrivs'].strip() == '1'
print('permissions-ok')
""",
        None,
    ),
    (
        "network_denied",
        """
import socket
for address, port in [('127.0.0.1', 8000), ('192.168.194.129', 8000), ('169.254.169.254', 80), ('1.1.1.1', 443)]:
    with socket.socket() as connection:
        connection.settimeout(0.5)
        assert connection.connect_ex((address, port)) != 0, 'network escape'
print('network-denied')
""",
        None,
    ),
    (
        "task_write_canary",
        "from pathlib import Path\nPath('/tmp/task-private-canary').write_text('previous-task')\nprint('created')",
        None,
    ),
    (
        "next_task_isolation",
        "from pathlib import Path\nassert not Path('/tmp/task-private-canary').exists()\nprint('isolated')",
        None,
    ),
    (
        "symlink_artifact_rejected",
        "from pathlib import Path\nPath(output_dir, 'escape.json').symlink_to('/etc/passwd')",
        {"EXECUTION_FAILED"},
    ),
    (
        "outside_output_not_exported",
        "from pathlib import Path\nPath(output_dir, '../hidden.json').write_text('{}')\nprint('outside-not-exported')",
        None,
    ),
    ("stdout_overflow", "print('x' * 70000)", {"EXECUTION_FAILED", "RESOURCE_LIMIT"}),
    (
        "forged_envelope_rejected",
        'import sys\nsys.__stdout__.write(\'{"status":"completed","stdout":"fake","artifacts":[]}\')',
        {"EXECUTION_FAILED"},
    ),
    (
        "cpu_deadline",
        "while True:\n    pass",
        {"EXECUTION_TIMEOUT", "EXECUTION_FAILED"},
    ),
    (
        "memory_limit",
        "blocks=[]\nwhile True:\n    blocks.append(bytearray(8 * 1024 * 1024))",
        {"EXECUTION_TIMEOUT", "EXECUTION_FAILED"},
    ),
    (
        "scratch_limit",
        """
from pathlib import Path
failed = False
for index in range(64):
    try:
        Path('/tmp/fill-' + str(index)).write_bytes(b'x' * 1048576)
    except OSError:
        failed = True
        break
assert failed and index <= 32, 'scratch size unenforced'
print('scratch-bounded')
""",
        None,
    ),
    (
        "process_limit",
        """
import os, signal, time, resource
assert resource.getrlimit(resource.RLIMIT_NPROC) == (2, 2)
try:
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
except (ValueError, PermissionError):
    pass
else:
    raise AssertionError('guest can raise its hard task limit')
children = []
limited = False
try:
    for _ in range(40):
        try:
            pid = os.fork()
        except OSError:
            limited = True
            break
        if pid == 0:
            time.sleep(25)
            os._exit(0)
        children.append(pid)
    assert limited and len(children) == 1, 'guest process limit unenforced'
finally:
    for pid in children:
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except ProcessLookupError:
            pass
print('processes-bounded')
""",
        None,
    ),
    (
        "detached_child_cleaned",
        """
import subprocess, sys
subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(25)'],
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                 start_new_session=True)
print('parent-finished')
""",
        None,
    ),
]


def check_runtime_hash():
    with RUNTIME.open("rb") as file:
        assert hashlib.file_digest(file, "sha256").hexdigest() == RUNTIME_HASH


async def verify(image):
    await asyncio.to_thread(check_runtime_hash)
    commands = ObservedCommands()
    information = await commands.execute(["info", "--format", "{{json .Runtimes}}"])
    runtime = json.loads(information.stdout)["runsc"]
    assert runtime["path"] == str(RUNTIME) and runtime["runtimeArgs"] == [
        "--platform=systrap"
    ]
    executor = SandboxExecutor(commands, image)
    results = []
    for name, code, expected in CASES:
        started = time.monotonic()
        item = {"case": name, "passed": False}
        try:
            value = await executor.run(code, DATA)
            if expected:
                raise AssertionError("expected rejection")
            if name == "analysis_and_artifacts":
                artifacts = {a.name: a for a in value.artifacts}
                assert set(artifacts) == {"summary.json", "counts.csv", "plot.png"}
                assert json.loads(artifacts["summary.json"].content) == {
                    "sum": 5,
                    "mean": 2.5,
                }
                assert artifacts["plot.png"].mime == "image/png"
                item["artifact_bytes"] = sum(len(a.content) for a in value.artifacts)
            elif name == "outside_output_not_exported":
                assert not value.artifacts
            item["passed"] = True
        except ResearchRejected as exc:
            item["code"] = exc.code
            item["passed"] = bool(expected and exc.code in expected)
        except (
            AssertionError,
            ValueError,
            RuntimeError,
            OSError,
            KeyError,
            TypeError,
        ) as exc:
            item["code"] = type(exc).__name__
        await commands.assert_removed()
        item["duration_ms"] = round((time.monotonic() - started) * 1000)
        results.append(item)
        print(json.dumps(item), flush=True)
    commands.starting.clear()
    task = asyncio.create_task(executor.run("import time; time.sleep(25)", DATA))
    await asyncio.wait_for(commands.starting.wait(), timeout=6)
    await asyncio.sleep(0.5)
    task.cancel()
    cancelled = False
    try:
        await task
    except asyncio.CancelledError:
        cancelled = True
    await commands.assert_removed()
    results.append({"case": "cancel_cleanup", "passed": cancelled})
    return {
        "status": "passed" if all(c["passed"] for c in results) else "failed",
        "image": image,
        "runtime_hash": RUNTIME_HASH,
        "cases": results,
        "configurations_checked": commands.configurations_checked,
        "python_enabled": False,
    }


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
            report = asyncio.run(verify(args.image))
        except (
            AssertionError,
            ValueError,
            RuntimeError,
            OSError,
            KeyError,
            TypeError,
        ) as exc:
            report = {"status": "failed", "code": type(exc).__name__}
        output.seek(0)
        json.dump(report, output, indent=2)
        output.truncate()
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps(report), flush=True)
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
