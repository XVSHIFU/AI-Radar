import json

import httpx
import pytest

from radar.model_stream import ModelStreamError, OpenAiCompatibleStream


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def event(body: dict) -> bytes:
    return b"data: " + json.dumps(body).encode() + b"\n\n"


@pytest.mark.asyncio
async def test_stream_is_incremental_preserves_base_path_and_records_usage():
    seen = {}

    def handler(request: httpx.Request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        chunks = [
            event({"id": "r1", "choices": [{"delta": {"content": "结"}, "finish_reason": None}]}),
            event(
                {"id": "r1", "choices": [{"delta": {"content": "论[1]"}, "finish_reason": "stop"}]}
            ),
            event(
                {
                    "id": "r1",
                    "choices": [],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
                }
            ),
            b"data: [DONE]\n\n",
        ]
        return httpx.Response(200, stream=Chunks(chunks))

    client = OpenAiCompatibleStream(
        "secret",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-flash",
        max_tokens=100,
        transport=httpx.MockTransport(handler),
    )
    try:
        parts = [item async for item in client.stream(system="s", user="u")]
    finally:
        await client.close()
    assert seen["path"] == "/v1/chat/completions"
    assert seen["body"]["thinking"] == {"type": "disabled"}
    assert [x.text for x in parts if x.text] == ["结", "论[1]"]
    assert parts[-1].done and parts[-1].usage.total_tokens == 13


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chunks", "code", "unknown"),
    [
        (
            [
                event({"choices": [{"delta": {"content": "x"}, "finish_reason": "length"}]}),
                b"data: [DONE]\n\n",
            ],
            "truncated_response",
            False,
        ),
        (
            [event({"choices": [{"delta": {"content": "x"}, "finish_reason": "stop"}]})],
            "incomplete_stream",
            True,
        ),
        (
            [event({"choices": [{"delta": {"tool_calls": [{}]}, "finish_reason": None}]})],
            "tool_output",
            False,
        ),
    ],
)
async def test_stream_rejects_incomplete_truncated_and_tool_output(chunks, code, unknown):
    client = OpenAiCompatibleStream(
        "secret",
        base_url="https://example.com/v1",
        model="m",
        max_tokens=10,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks))),
    )
    try:
        with pytest.raises(ModelStreamError) as caught:
            _ = [x async for x in client.stream(system="s", user="u")]
    finally:
        await client.close()
    assert caught.value.code == code and caught.value.unknown is unknown


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body", [None, [], {"choices": {}}, {"choices": [None]}, {"choices": [{"delta": []}]}]
)
async def test_malformed_valid_json_chunks_become_stream_errors(body):
    chunks = [b"data: " + json.dumps(body).encode() + b"\n\n"]
    client = OpenAiCompatibleStream(
        "secret",
        base_url="https://example.com/v1",
        model="m",
        max_tokens=10,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks))),
    )
    try:
        with pytest.raises(ModelStreamError) as caught:
            _ = [item async for item in client.stream(system="s", user="u")]
    finally:
        await client.close()
    assert caught.value.code == "invalid_stream"


@pytest.mark.asyncio
async def test_first_delta_is_available_before_done_is_consumed():
    chunks = [
        event({"choices": [{"delta": {"content": "first"}, "finish_reason": None}]}),
        event({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        b"data: [DONE]\n\n",
    ]
    client = OpenAiCompatibleStream(
        "secret",
        base_url="https://example.com/v1",
        model="m",
        max_tokens=10,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks))),
    )
    stream = client.stream(system="s", user="u")
    try:
        first = await anext(stream)
        assert first.text == "first" and not first.done
    finally:
        await stream.aclose()
        await client.close()


@pytest.mark.asyncio
async def test_data_after_finish_is_rejected():
    chunks = [
        event({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
        event({"choices": [{"delta": {"content": "late"}, "finish_reason": None}]}),
        b"data: [DONE]\n\n",
    ]
    client = OpenAiCompatibleStream(
        "secret",
        base_url="https://example.com/v1",
        model="m",
        max_tokens=10,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Chunks(chunks))),
    )
    try:
        with pytest.raises(ModelStreamError) as caught:
            _ = [item async for item in client.stream(system="s", user="u")]
    finally:
        await client.close()
    assert caught.value.code == "data_after_finish"
