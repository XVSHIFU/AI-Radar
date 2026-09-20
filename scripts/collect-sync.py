"""Collect public feeds locally, then atomically import through SSH; no model calls.

Run with the project's backend Python environment. Settings and state stay local.
"""

import argparse
import asyncio
import base64
import hashlib
import ipaddress
import json
import os
import shlex
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx
from radar.article_rules import accept_feed_entry
from radar.ingest.core import canonicalize_url, fetch_public, parse_document, parse_feed
from radar.ingest.public_transport import PublicAsyncTransport


def save(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


@contextmanager
def single_run(path):
    with path.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


async def download(client, url, proxy):
    if not proxy:
        result = await fetch_public(client, url)
        return result.final_url, result.body
    # A trusted operator-configured proxy resolves DNS itself (including fake-IP setups).
    # This CLI takes only operator-maintained feeds, never public user input.
    for _ in range(6):
        url = canonicalize_url(url)
        host = urlsplit(url).hostname
        if host == "localhost" or "." not in host:
            raise ValueError("public source hostname required")
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            addr = None
        if addr and not addr.is_global:
            raise ValueError("private address rejected")
        async with client.stream("GET", url, timeout=25) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            result = bytearray()
            async for chunk in response.aiter_bytes():
                result.extend(chunk)
                if len(result) > 5 * 1024 * 1024:
                    raise ValueError("source response exceeds 5 MiB")
            return url, bytes(result)
    raise ValueError("too many redirects")


def send(config, packet):
    receiver = Path(__file__).with_name("import-collected.py").read_bytes()
    code = (
        "import base64;exec(compile(base64.b64decode("
        + repr(base64.b64encode(receiver).decode())
        + "),'import-collected.py','exec'))"
    )
    command = shlex.join(["docker", "exec", "-i", config["container"], "python", "-c", code])
    target = config["ssh"]
    if target.startswith("-") or any(c.isspace() for c in target):
        raise ValueError("invalid SSH target")
    result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
            target,
            command,
        ],
        input=json.dumps(packet["batch"]).encode(),
        capture_output=True,
        timeout=240,
        check=False,
    )
    if result.returncode:
        # Do not log connection strings or arbitrary remote exception payloads.
        raise RuntimeError(f"SSH import failed (exit {result.returncode}); pending batch retained")
    receipt = json.loads(result.stdout)
    if receipt.get("id") != packet["batch"]["id"]:
        raise RuntimeError("unexpected import receipt; pending batch retained")
    print(json.dumps(receipt), flush=True)


async def collect(config, state):
    batch = {
        "format": 1,
        "id": str(uuid4()),
        "limit": config.get("limit", 30),
        "feeds": [],
        "errors": [],
    }
    if not 1 <= batch["limit"] <= 30:
        raise ValueError("limit must be between 1 and 30")
    fingerprints = dict(state.get("articles", {}))
    proxy = config.get("proxy")
    options = {"proxy": proxy} if proxy else {"transport": PublicAsyncTransport()}
    async with httpx.AsyncClient(**options, trust_env=False, follow_redirects=False) as client:
        for source in config["feeds"]:
            name, url = source["name"], canonicalize_url(source["url"])
            try:
                _, raw = await download(client, url, proxy)
                entries = [e for e in parse_feed(raw) if accept_feed_entry(name, e.title, e.tags)][
                    : batch["limit"]
                ]
            except (httpx.HTTPError, OSError, ValueError) as exc:
                batch["errors"].append(f"{name}: feed {type(exc).__name__}")
                continue
            feed = {
                "name": name,
                "url": url,
                "rss": base64.b64encode(raw).decode(),
                "bodies": {},
            }
            for entry in entries:
                fingerprint = hashlib.sha256(
                    json.dumps([entry.title, entry.excerpt, entry.published, entry.tags]).encode()
                ).hexdigest()
                if fingerprints.get(entry.url) == fingerprint:
                    continue
                try:
                    final, body = await download(client, entry.url, proxy)
                    parse_document(body)  # Reject unusable bodies before sending.
                    feed["bodies"][entry.url] = {
                        "url": final,
                        "html": base64.b64encode(body).decode(),
                    }
                    fingerprints[entry.url] = fingerprint
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    batch["errors"].append(f"{name}: article {type(exc).__name__} ({entry.url})")
                await asyncio.sleep(config.get("delay_seconds", 1))
            batch["feeds"].append(feed)
            print(
                f"{name}: {len(entries)} entries, {len(feed['bodies'])} bodies",
                flush=True,
            )
    return {"batch": batch, "state": {"articles": fingerprints}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    folder = args.config.resolve().parent / "collect-sync-state"
    folder.mkdir(exist_ok=True)
    with single_run(folder / "lock"):
        pending, state_file = folder / "pending.json", folder / "state.json"
        if pending.exists():
            packet = json.loads(pending.read_text(encoding="utf-8"))
            send(config, packet)
            save(state_file, packet["state"])
            pending.unlink()
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
        packet = asyncio.run(collect(config, state))
        if not packet["batch"]["feeds"]:
            raise RuntimeError("No feeds collected: " + "; ".join(packet["batch"]["errors"]))
        save(pending, packet)
        send(config, packet)
        save(state_file, packet["state"])
        pending.unlink()
        save(
            folder / "last-run.json",
            {
                "finished_at": datetime.now(UTC).isoformat(),
                "errors": packet["batch"]["errors"],
                "batch_id": packet["batch"]["id"],
            },
        )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
