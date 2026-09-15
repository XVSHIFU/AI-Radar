"""Bounded data transfer for untrusted Python; parsing never executes generated code."""

from __future__ import annotations

import base64
import binascii
import csv
import io
import re
import struct
import zlib
from dataclasses import dataclass
from typing import Any

from .research_guard import ResearchRejected, canonical
from .research_stream import strict_json

MAX_DATASET_BYTES = 2097152
MAX_CODE_BYTES = 16384
MAX_INPUT_BYTES = MAX_DATASET_BYTES + 131072
MAX_ARTIFACT_BYTES = 1048576
MAX_STDOUT_BYTES = 65536
MAX_RESPONSE_BYTES = 1572864
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,59}\.(json|csv|png)\Z")


def sandbox_input(code: str, datasets: list[dict[str, Any]]) -> bytes:
    try:
        if not isinstance(code, str) or not code.strip() or len(code.encode()) > MAX_CODE_BYTES:
            raise ResearchRejected("INVALID_ARGUMENT")
        if not isinstance(datasets, list) or not 1 <= len(datasets) <= 4:
            raise ResearchRejected("INVALID_ARGUMENT")
        if any(not isinstance(d, dict) or not isinstance(d.get("rows"), list) for d in datasets):
            raise ResearchRejected("INVALID_ARGUMENT")
        if sum(len(dataset["rows"]) for dataset in datasets) > 10000:
            raise ResearchRejected("RESOURCE_LIMIT")
        data = canonical(datasets).encode()
        payload = canonical({"code": code, "datasets": datasets}).encode()
        if len(data) > MAX_DATASET_BYTES or len(payload) > MAX_INPUT_BYTES:
            raise ResearchRejected("RESOURCE_LIMIT")
        return payload
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise ResearchRejected("INVALID_ARGUMENT") from exc


@dataclass(frozen=True)
class SandboxArtifact:
    name: str
    mime: str
    content: bytes


@dataclass(frozen=True)
class SandboxResult:
    stdout: str
    artifacts: tuple[SandboxArtifact, ...]


def _png(data: bytes) -> bytes:
    """Validate a bounded non-interlaced 8-bit PNG and drop optional metadata.

    Palette PNGs are deliberately excluded; matplotlib exports RGB/RGBA. Inflate
    at most the exact raster size plus one byte, including when input is a bomb.
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG signature")
    offset, chunks, compressed = 8, [], bytearray()
    header = False
    ended_data = False
    transparency = False
    color, stride, height = 0, 0, 0
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + size + 12
        if (
            end > len(data)
            or zlib.crc32(data[offset + 4 : end - 4]) != struct.unpack_from(">I", data, end - 4)[0]
        ):
            raise ValueError("PNG chunk")
        payload = data[offset + 8 : end - 4]
        if not header:
            if kind != b"IHDR" or size != 13:
                raise ValueError("PNG header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (
                not 1 <= width <= 4096
                or not 1 <= height <= 4096
                or width * height > 4194304
                or depth != 8
                or color not in {0, 2, 4, 6}
                or compression
                or filtering
                or interlace
            ):
                raise ValueError("PNG dimensions/format")
            stride = width * {0: 1, 2: 3, 4: 2, 6: 4}[color] + 1
            header = True
        elif kind == b"IHDR":
            raise ValueError("duplicate PNG header")
        if kind == b"IDAT":
            if ended_data:
                raise ValueError("nonconsecutive PNG data")
            compressed.extend(payload)
        elif compressed:
            ended_data = True
        if kind == b"tRNS":
            if transparency or compressed or color not in {0, 2} or size != {0: 2, 2: 6}[color]:
                raise ValueError("PNG transparency")
            if any(value > 255 for (value,) in struct.iter_unpack(">H", payload)):
                raise ValueError("PNG transparency range")
            transparency = True
        if kind in {b"IHDR", b"IDAT", b"IEND", b"tRNS"}:
            chunks.append(data[offset:end])
        elif kind not in {b"tEXt", b"pHYs", b"gAMA", b"sRGB", b"cHRM"}:
            raise ValueError("unsupported PNG chunk")
        if kind == b"IEND":
            if size or not compressed or end != len(data):
                raise ValueError("PNG trailer")
            inflater = zlib.decompressobj()
            expected = stride * height
            pixels = inflater.decompress(compressed, expected + 1)
            if (
                len(pixels) != expected
                or not inflater.eof
                or inflater.unconsumed_tail
                or inflater.unused_data
                or any(pixels[row * stride] > 4 for row in range(height))
            ):
                raise ValueError("PNG raster")
            return data[:8] + b"".join(chunks)
        offset = end
    raise ValueError("incomplete PNG")


def _csv(data: bytes) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    for count, row in enumerate(
        csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
    ):
        if count > 10000 or len(row) > 128:
            raise ValueError("CSV size")
        safe = []
        for value in row:
            if "\0" in value or len(value.encode()) > 65536:
                raise ValueError("CSV field")
            candidate = re.sub(r"^[\s\ufeff]+", "", value)
            if candidate.startswith(("=", "+", "-", "@")) and not re.fullmatch(
                r"-?\d+(?:\.\d+)?", candidate
            ):
                value = "'" + value
            safe.append(value)
        writer.writerow(safe)
    return output.getvalue().encode("utf-8")


def sandbox_result(raw: bytes) -> SandboxResult:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ResearchRejected("RESOURCE_LIMIT")
    try:
        body = strict_json(raw.decode("utf-8"))
        if not isinstance(body, dict) or body.get("status") != "completed":
            raise ValueError("execution failed")
        if set(body) != {"status", "stdout", "artifacts"} or not isinstance(body["stdout"], str):
            raise ValueError("invalid result")
        if (
            len(body["stdout"].encode()) > MAX_STDOUT_BYTES
            or not isinstance(body["artifacts"], list)
            or len(body["artifacts"]) > 8
        ):
            raise ValueError("result size")
        artifacts, names, size = [], set(), 0
        for item in body["artifacts"]:
            if not isinstance(item, dict) or set(item) != {"name", "data"}:
                raise ValueError("artifact shape")
            name = item["name"]
            if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
                raise ValueError("artifact name")
            content = base64.b64decode(item["data"], validate=True)
            size += len(content)
            if size > MAX_ARTIFACT_BYTES:
                raise ValueError("artifact size")
            names.add(name)
            if name.endswith(".png"):
                content, mime = _png(content), "image/png"
            elif name.endswith(".csv"):
                content, mime = _csv(content), "text/csv"
            else:
                content, mime = (
                    canonical(strict_json(content.decode("utf-8"))).encode(),
                    "application/json",
                )
            artifacts.append(SandboxArtifact(name, mime, content))
        if sum(len(artifact.content) for artifact in artifacts) > MAX_ARTIFACT_BYTES:
            raise ValueError("normalized artifact size")
        return SandboxResult(body["stdout"], tuple(artifacts))
    except (
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        UnicodeError,
        binascii.Error,
        csv.Error,
        zlib.error,
    ) as exc:
        raise ResearchRejected("EXECUTION_FAILED") from exc
