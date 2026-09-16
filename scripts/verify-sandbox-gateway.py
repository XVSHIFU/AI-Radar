"""Separate-process loopback HTTP + real gVisor + owner download acceptance.

Synthetic data only; no provider calls, service restarts or public Python enable.
The private token is generated in RAM and passed on child stdin, never argv/logs.
"""

import argparse
import asyncio
import importlib.util
import json
import os
import secrets
import socket
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI
from radar.public_assistant import COOKIE
from radar.public_identity import PublicIdentity
from radar.research_artifacts import ArtifactStore, router
from radar.research_guard import ResearchGuard, ResearchRejected
from radar.research_python import ResearchPython
from radar.sandbox_client import SandboxClient
from radar.sandbox_executor import SandboxExecutor
from radar.sandbox_http import controller_app


def acceptance_module():
    spec = importlib.util.spec_from_file_location(
        "sandbox_acceptance", Path(__file__).with_name("verify-python-sandbox.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def serve(image, descriptor):
    acceptance = acceptance_module()
    acceptance.check_runtime_hash()
    token = sys.stdin.readline().strip()

    class Commands(acceptance.ObservedCommands):
        async def execute(self, arguments, **kwargs):
            result = await super().execute(arguments, **kwargs)
            if arguments[0] == "create" and result.code == 0:
                print(
                    json.dumps({"stage": "created", "count": len(self.names)}),
                    flush=True,
                )
            return result

    commands = Commands()

    class Executor(SandboxExecutor):
        async def run(self, code, datasets):
            try:
                return await super().run(code, datasets)
            finally:
                await commands.assert_removed()
                print(
                    json.dumps({"stage": "removed", "count": len(commands.names)}),
                    flush=True,
                )

    app = controller_app(Executor(commands, image), token)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    server.run(sockets=[socket.socket(fileno=descriptor)])


async def verify(image):
    acceptance = acceptance_module()
    acceptance.check_runtime_hash()
    commands = acceptance.ObservedCommands()
    runtime_info = await commands.execute(["info", "--format", "{{json .Runtimes}}"])
    runtime = json.loads(runtime_info.stdout)["runsc"]
    assert runtime["path"] == str(acceptance.RUNTIME)
    assert runtime["runtimeArgs"] == ["--platform=systrap"]
    token = secrets.token_urlsafe(32)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 8092))
    listener.listen(8)
    child = None
    reader = None
    stages = []
    try:
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            str(Path(__file__).resolve()),
            "--serve",
            image,
            "--socket",
            str(listener.fileno()),
            pass_fds=(listener.fileno(),),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        child.stdin.write((token + "\n").encode())
        await child.stdin.drain()
        child.stdin.close()
        listener.close()

        async def observe():
            async for line in child.stdout:
                stages.append(json.loads(line))

        reader = asyncio.create_task(observe())

        async def wait_stage(stage, count):
            async with asyncio.timeout(7):
                while {"stage": stage, "count": count} not in stages:
                    if child.returncode is not None:
                        raise RuntimeError("controller stopped")
                    await asyncio.sleep(0.02)

        async with httpx.AsyncClient(trust_env=False) as http:
            async with asyncio.timeout(8):
                while True:
                    try:
                        denied = await http.post(
                            "http://127.0.0.1:8092/v1/execute", content=b"bad"
                        )
                        assert denied.status_code == 401
                        break
                    except httpx.ConnectError:
                        await asyncio.sleep(0.1)
            identity = PublicIdentity(secrets.token_hex(32))
            cookie = identity.issue()
            guard = ResearchGuard(
                uuid4(),
                identity.subject(cookie),
                datetime.now(UTC) + timedelta(seconds=90),
            )
            dataset_id = str(uuid4())
            datasets = {dataset_id: {"dataset_id": dataset_id, **acceptance.DATA[0]}}
            artifacts = ArtifactStore()
            client = SandboxClient(http, "http://127.0.0.1:8092", token)
            tool = ResearchPython(guard, datasets, client, artifacts)
            try:
                await tool.execute({"code": "print(1)", "dataset_ids": [str(uuid4())]})
                raise AssertionError("foreign dataset accepted")
            except ResearchRejected as exc:
                assert exc.code == "DATASET_NOT_FOUND"
            started = time.monotonic()
            result = await tool.execute(
                {"code": acceptance.CASES[0][1], "dataset_ids": [dataset_id]}
            )
            analysis_ms = round((time.monotonic() - started) * 1000)
            await wait_stage("removed", 1)
            assert len(result["artifacts"]) == 3
            api = FastAPI()
            api.state.public_identity = identity
            api.state.research_artifacts = artifacts
            api.include_router(router)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api), base_url="http://api"
            ) as public:
                for artifact in result["artifacts"]:
                    url = artifact["download_url"]
                    public.cookies.set(COOKIE, identity.issue())
                    assert (await public.get(url)).status_code == 404
                    public.cookies.set(COOKIE, cookie)
                    download = await public.get(url)
                    assert download.status_code == 200
                    assert download.headers["x-content-type-options"] == "nosniff"
                    assert download.headers["content-disposition"].startswith(
                        "attachment;"
                    )
                    if artifact["name"] == "summary.json":
                        assert download.json() == {"sum": 5, "mean": 2.5}
            replay = await http.post(
                "http://127.0.0.1:8092/v1/execute",
                headers={"Authorization": "Bearer " + token},
                json={
                    "job_id": str(guard.run_id),
                    "code": "print(0)",
                    "datasets": list(datasets.values()),
                },
            )
            assert replay.status_code == 409
            slow = asyncio.create_task(
                client.run(uuid4(), "while True: pass", list(datasets.values()))
            )
            try:
                await wait_stage("created", 2)
                await asyncio.sleep(0.2)
                started = time.monotonic()
                slow.cancel()
                await asyncio.gather(slow, return_exceptions=True)
                await wait_stage("removed", 2)
                cancel_ms = round((time.monotonic() - started) * 1000)
                assert cancel_ms < 6000
            finally:
                slow.cancel()
                await asyncio.gather(slow, return_exceptions=True)
            return {
                "status": "passed",
                "image": image,
                "python_enabled": False,
                "controller_separate_process": True,
                "containers_checked_removed": 2,
                "analysis_ms": analysis_ms,
                "disconnect_cleanup_ms": cancel_ms,
                "artifact_count": 3,
                "cross_owner_download": "rejected",
                "foreign_dataset": "rejected",
                "replay": "rejected",
                "model_calls": 0,
            }
    finally:
        listener.close()
        if child and child.returncode is None:
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), 10)
            except TimeoutError:
                child.kill()
                await child.wait()
        if reader:
            await reader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--serve")
    parser.add_argument("--socket", type=int)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.socket)
        return
    if not args.image or not args.report:
        parser.error("--image and --report are required")
    descriptor = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        try:
            result = asyncio.run(verify(args.image))
        except (
            AssertionError,
            ValueError,
            RuntimeError,
            OSError,
            KeyError,
            TypeError,
            httpx.HTTPError,
            ResearchRejected,
        ) as exc:
            result = {"status": "failed", "error": type(exc).__name__}
            # No exception arguments: operator credentials must not reach a report.
        json.dump(result, output, indent=2)
    print(json.dumps(result), flush=True)
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
