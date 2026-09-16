"""Single-request SSE capture for a separately authorized isolated evaluation.

Library only: no configured endpoint, model key, CLI runner, or automatic retry.
Token usage/model-call counts must later come from the isolated server ledger.
"""

import codecs
import json
import time

import httpx

LIMIT = 1_048_576


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate stream key")
            value[key] = item
        return value

    def invalid(_):
        raise ValueError("nonfinite stream value")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


async def capture(
    client, payload, *, cancel_on_first_token=False, clock=time.monotonic
):
    """Send once. Caller owns client authorization, service isolation and cost ceiling."""
    started = clock()
    record = {
        "status": "failed",
        "answer": "",
        "citations": [],
        "artifacts": [],
        "metadata": {},
        "timeline": [],
        "client_checks": {},
        "metrics": {
            "model_calls": None,
            "input_tokens": None,
            "output_tokens": None,
            "first_token_ms": None,
            "duration_ms": None,
        },
    }
    sources, artifacts, terminal, error, sequence, total = [], [], False, False, 0, 0

    def accept(block):
        nonlocal sources, artifacts, terminal, error, sequence
        if not block or block.startswith(":"):
            return False
        if terminal:
            raise ValueError("data after terminal event")
        lines = block.split("\n")
        names = [line[6:].strip() for line in lines if line.startswith("event:")]
        data = [line[5:].lstrip() for line in lines if line.startswith("data:")]
        if len(names) != 1 or not data:
            raise ValueError("invalid SSE frame")
        name, item = names[0], strict_json("\n".join(data))
        if not isinstance(item, dict):
            raise TypeError("SSE object required")
        elapsed = round((clock() - started) * 1000, 3)
        if len(record["timeline"]) >= 4096:
            raise ValueError("too many SSE frames")
        record["timeline"].append({"event": name, "elapsed_ms": elapsed})
        if name == "meta":
            record["metadata"] = item
        elif name == "reset":
            if not isinstance(item.get("text"), str):
                raise ValueError("invalid reset")
            record["answer"], sequence = item["text"], 0
            sources, artifacts = [], []
        elif name == "token":
            if (
                not isinstance(item.get("text"), str)
                or type(item.get("seq")) is not int
                or item["seq"] != sequence + 1
            ):
                raise ValueError("invalid token sequence")
            sequence += 1
            record["answer"] += item["text"]
            if item["text"].strip() and record["metrics"]["first_token_ms"] is None:
                record["metrics"]["first_token_ms"] = elapsed
                if cancel_on_first_token:
                    record["status"] = "cancelled"
                    record["client_checks"] = {
                        "draft_retained": bool(record["answer"]),
                        "not_completed": True,
                    }
                    # No claim about server retries until the ledger is inspected.
                    return True
        elif name in ("sources", "artifacts"):
            if not isinstance(item.get("items"), list):
                raise ValueError("invalid result items")
            if name == "sources":
                sources = item["items"]
            else:
                artifacts = item["items"]
        elif name == "error":
            error = True
            record["error_code"] = item.get("code", "STREAM_ERROR")
        elif name == "done":
            terminal = True
            if item.get("status") not in ("completed", "failed", "cancelled"):
                raise ValueError("invalid terminal status")
            record["status"] = "failed" if error else item["status"]
            record["terminal"] = item
        elif name != "status":
            raise ValueError("unknown SSE event")
        if len(record["answer"].encode()) > 65536:
            raise ValueError("answer limit")
        return False

    try:
        async with client.stream(
            "POST", "/api/v1/ask/stream", json=payload
        ) as response:
            record["http_status"] = response.status_code
            if response.status_code != 200:
                record["status"] = "rejected"
                return record
            if (
                response.headers.get("content-type", "").split(";")[0]
                != "text/event-stream"
            ):
                raise ValueError("SSE content type required")
            decoder = codecs.getincrementaldecoder("utf-8")("strict")
            pending = ""
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > LIMIT:
                    raise ValueError("stream limit")
                pending += decoder.decode(chunk)
                pending = pending.replace("\r\n", "\n")
                while "\n\n" in pending:
                    block, pending = pending.split("\n\n", 1)
                    if accept(block):
                        return record
                if len(pending.encode()) > 262144:
                    raise ValueError("frame limit")
            pending += decoder.decode(b"", final=True)
            if pending.strip() or not terminal:
                raise ValueError("stream ended before a complete terminal frame")
            if record["status"] == "completed":
                record["citations"], record["artifacts"] = sources, artifacts
    except (httpx.HTTPError, TypeError, ValueError, UnicodeError, RecursionError):
        record["status"] = "failed"
        record["error_code"] = "CAPTURE_INCOMPLETE"
        record["citations"], record["artifacts"] = [], []
    finally:
        record["metrics"]["duration_ms"] = round((clock() - started) * 1000, 3)
    return record
