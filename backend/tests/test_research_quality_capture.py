import json

import httpx
import pytest
from test_research_quality_seed import load

capture = load("research_quality_capture")


def frame(name, **body):
    return f"event: {name}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n".encode()


class Stream(httpx.AsyncByteStream):
    def __init__(self, pieces):
        self.pieces, self.closed, self.read = pieces, False, 0

    async def __aiter__(self):
        for piece in self.pieces:
            self.read += 1
            yield piece

    async def aclose(self):
        self.closed = True


async def collect(pieces, *, cancel=False, status=200):
    requests, clock = [], [0.0]
    stream = Stream(pieces)

    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={"content-type": "text/event-stream"}, stream=stream)

    def tick():
        clock[0] += 0.1
        return clock[0]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://fixture"
    ) as client:
        result = await capture.capture(
            client, {"question": "fixture"}, cancel_on_first_token=cancel, clock=tick
        )
    assert len(requests) == 1
    assert stream.closed
    return result, stream


async def test_byte_split_utf8_and_reset_keep_only_final_answer_and_real_first_token_time():
    wire = b"".join(
        [
            frame("meta", protocol_version=2),
            frame("status", phase="researching"),
            frame("reset", turn=1, text=""),
            frame("token", seq=1, text="草稿"),
            frame("reset", turn=2, text=""),
            frame("token", seq=1, text="正式回答[1]"),
            frame("sources", items=[{"index": 1}]),
            frame("artifacts", items=[{"name": "plot.png"}]),
            frame("done", status="completed"),
        ]
    )
    result, _ = await collect([wire[i : i + 1] for i in range(len(wire))])
    assert result["status"] == "completed" and result["answer"] == "正式回答[1]"
    assert result["citations"] == [{"index": 1}]
    assert result["metrics"]["first_token_ms"] == 400
    assert result["metrics"]["model_calls"] is None
    assert result["metrics"]["input_tokens"] is None
    assert result["metrics"]["first_token_ms"] < result["metrics"]["duration_ms"]


async def test_cancel_closes_stream_at_first_content_without_reading_or_publishing_later_frames():
    result, stream = await collect(
        [
            frame("status", phase="generating"),
            frame("token", seq=1, text="片段"),
            frame("sources", items=[{"index": 1}]),
            frame("done", status="completed"),
        ],
        cancel=True,
    )
    assert result["status"] == "cancelled" and result["answer"] == "片段"
    assert stream.read == 2
    assert result["citations"] == result["artifacts"] == []
    assert "no_automatic_retry" not in result["client_checks"]


@pytest.mark.parametrize(
    "tail",
    [
        b"",
        b"event: done\ndata: {bad}\n\n",
        b'event: done\ndata: {"status":"failed","status":"completed"}\n\n',
        frame("done", status="failed"),
        frame("done", status="completed") + frame("token", seq=2, text="late"),
        frame("error", code="BROKEN") + frame("done", status="completed"),
    ],
)
async def test_malformed_failed_or_incomplete_stream_never_publishes_sources(tail):
    result, _ = await collect(
        [frame("token", seq=1, text="未完成[1]"), frame("sources", items=[{"index": 1}]), tail]
    )
    assert result["status"] == "failed"
    assert result["citations"] == result["artifacts"] == []


async def test_preflight_rejection_is_recorded_without_retry_or_assumed_model_usage():
    result, _ = await collect([], status=503)
    assert result["status"] == "rejected"
    assert result["metrics"]["model_calls"] is None
    assert result["metrics"]["first_token_ms"] is None
