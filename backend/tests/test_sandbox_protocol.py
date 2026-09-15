import base64
import json
import struct
import zlib

import pytest

from radar.research_guard import ResearchRejected
from radar.sandbox_protocol import MAX_INPUT_BYTES, sandbox_input, sandbox_result


def chunk(kind, payload=b""):
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload))
    )


def png(pixels=b"\0\xff\0\0\xff", *, width=1, height=1, compressed=None, extra=b""):
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + extra
        + chunk(b"IDAT", zlib.compress(pixels) if compressed is None else compressed)
        + chunk(b"IEND")
    )


def result(name, data):
    return json.dumps(
        {
            "status": "completed",
            "stdout": "",
            "artifacts": [{"name": name, "data": base64.b64encode(data).decode()}],
        }
    ).encode()


def test_bounded_input_accepts_escaped_code_and_rejects_nonfinite_or_malformed_data():
    payload = sandbox_input("\x00" * 16384, [{"rows": [{"text": "x" * 2097100}]}])
    assert len(payload) <= MAX_INPUT_BYTES
    assert json.loads(payload)["code"] == "\x00" * 16384
    for datasets in [[], [{}], [{"rows": None}], [{"rows": [{"v": float("nan")}]}]]:
        with pytest.raises(ResearchRejected, match="INVALID_ARGUMENT"):
            sandbox_input("print(1)", datasets)
    for datasets in [[{"rows": [{}] * 10001}], [{"rows": [{"v": "x" * 2097152}]}]]:
        with pytest.raises(ResearchRejected, match="RESOURCE_LIMIT"):
            sandbox_input("print(1)", datasets)


@pytest.mark.parametrize(
    "name", ["../x.json", "/x.csv", "C:x.png", "a.svg", "a.html", "a.json/evil"]
)
def test_artifact_paths_and_executable_types_rejected(name):
    with pytest.raises(ResearchRejected, match="EXECUTION_FAILED"):
        sandbox_result(result(name, b"{}"))


def test_csv_formula_neutralization_preserves_numeric_data():
    value = sandbox_result(result("report.csv", b"name,value\na,=1+1\nb,-12.5\nc, @SUM(A1)\n"))
    assert value.artifacts[0].content == b"name,value\r\na,'=1+1\r\nb,-12.5\r\nc,' @SUM(A1)\r\n"


@pytest.mark.parametrize("data", [b'{"a":1,"a":2}', b'{"a":NaN}', b"not json"])
def test_json_artifacts_are_strict(data):
    with pytest.raises(ResearchRejected, match="EXECUTION_FAILED"):
        sandbox_result(result("report.json", data))


def test_png_strips_metadata_and_validates_raster():
    artifact = sandbox_result(
        result("plot.png", png(extra=chunk(b"tEXt", b"note\0private")))
    ).artifacts[0]
    assert artifact.content == png()
    assert artifact.mime == "image/png"


@pytest.mark.parametrize(
    "data",
    [
        png(width=4097),
        png(height=4096, width=4096),
        png(pixels=b"\5\xff\0\0\xff"),
        png(pixels=b""),
        png(pixels=b"\0" * 1000000),
        png(compressed=b"invalid deflate"),
        png(compressed=zlib.compress(b"\0\xff\0\0\xff") + b"trailing"),
        png() + b"trailing",
        png()[:-1] + b"x",
        png(extra=chunk(b"IHDR", b"")),
        png(extra=chunk(b"tRNS", b"\0\0")),
    ],
)
def test_invalid_or_bomb_png_rejected(data):
    with pytest.raises(ResearchRejected, match="EXECUTION_FAILED"):
        sandbox_result(result("plot.png", data))


def test_duplicate_artifacts_and_oversized_output_rejected():
    body = json.loads(result("a.json", b"{}"))
    body["artifacts"] *= 2
    with pytest.raises(ResearchRejected, match="EXECUTION_FAILED"):
        sandbox_result(json.dumps(body).encode())
    with pytest.raises(ResearchRejected, match="RESOURCE_LIMIT"):
        sandbox_result(b" " * 1572865)
    with pytest.raises(ResearchRejected, match="EXECUTION_FAILED"):
        sandbox_result(result("a.json", b'"' + b"x" * 1048576 + b'"'))
    body["artifacts"] = []
    body["stdout"] = "x" * 65537
    with pytest.raises(ResearchRejected, match="EXECUTION_FAILED"):
        sandbox_result(json.dumps(body).encode())
