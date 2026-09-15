import asyncio
import json

import httpx
import pytest

from radar.model_stream import ModelStreamError
from radar.research_stream import ResearchModelStream


def event(delta=None, finish=None, **extra):
    body = {"choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}], **extra}
    return b"data: " + json.dumps(body).encode() + b"\n\n"


class Chunks(httpx.AsyncByteStream):
    def __init__(self, blocks, gate=None):
        self.blocks = blocks
        self.gate = gate
        self.closed = False

    async def __aiter__(self):
        for index, block in enumerate(self.blocks):
            if index == 1 and self.gate:
                await self.gate.wait()
            yield block

    async def aclose(self):
        self.closed = True


def client_for(chunks, seen=None, status=200):
    def handle(request):
        if seen is not None:
            seen.append((str(request.url), json.loads(request.content)))
        return httpx.Response(status, stream=chunks)

    return ResearchModelStream(
        "test-provider-key",
        base_url="https://api.deepseek.com/v1",
        model="configured-model",
        max_tokens=1600,
        transport=httpx.MockTransport(handle),
    )


def body(client):
    return client.request_body([{"role": "user", "content": "q"}], [], 1000)


async def test_real_incremental_text_and_disconnect_close_transport_without_retry():
    gate = asyncio.Event()
    chunks = Chunks([event({"content": "first"}), event({}, "stop"), b"data: [DONE]\n\n"], gate)
    seen = []
    client = client_for(chunks, seen)
    stream = client.stream_request(body(client))
    try:
        first = await asyncio.wait_for(anext(stream), timeout=0.2)
        assert first.text == "first" and first.finish is None
    finally:
        await stream.aclose()
        await client.close()
    assert chunks.closed and len(seen) == 1


async def test_fragmented_tool_arguments_assembled_only_after_done_and_usage_not_lost():
    chunks = Chunks(
        [
            event(
                {
                    "reasoning_content": "private thought",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "search_events", "arguments": '{"query":"模'},
                        }
                    ],
                }
            ),
            event({"tool_calls": [{"index": 0, "function": {"arguments": '型"}'}}]}),
            event(
                {},
                "tool_calls",
                usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            ),
            b"data: [DONE]\n\n",
        ]
    )
    seen = []
    client = client_for(chunks, seen)
    try:
        parts = [part async for part in client.stream_request(body(client))]
    finally:
        await client.close()
    assert len(parts) == 1 and parts[0].text == ""
    result = parts[0]
    assert result.tools[0].arguments == {"query": "模型"}
    assert result.tools[0].id == "call-1" and result.finish == "tool_calls"
    assert result.usage.total_tokens == 120
    assert seen[0][0] == "https://api.deepseek.com/v1/chat/completions"
    assert seen[0][1]["thinking"] == {"type": "disabled"}
    assert "test-provider-key" not in repr(parts) and "private thought" not in repr(parts)


@pytest.mark.parametrize("arguments", ['{"q":1,"q":2}', '{"q":NaN}', "[]", '{"q":'])
async def test_malformed_arguments_never_become_executable(arguments):
    chunks = Chunks(
        [
            event(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-1",
                            "function": {"name": "search_events", "arguments": arguments},
                        }
                    ]
                },
                "tool_calls",
            ),
            b"data: [DONE]\n\n",
        ]
    )
    client = client_for(chunks)
    try:
        with pytest.raises(ModelStreamError, match="invalid research provider stream"):
            _ = [part async for part in client.stream_request(body(client))]
    finally:
        await client.close()
    assert chunks.closed


@pytest.mark.parametrize(
    "blocks",
    [
        [event({"content": "draft"}, "stop")],  # No DONE is never success.
        [event({}, "stop"), event({"content": "late"}), b"data: [DONE]\n\n"],
        [event({"tool_calls": [{"index": 6}]})],
        [event({}, "stop", usage={"prompt_tokens": -1}), b"data: [DONE]\n\n"],
        [b"data: " + b"x" * 66000],
        [b"data: " + b"\xff\n\n"],
        [
            event(
                {
                    "tool_calls": [
                        {"index": i, "id": "same", "function": {"name": "x", "arguments": "{}"}}
                        for i in range(2)
                    ]
                },
                "tool_calls",
            ),
            b"data: [DONE]\n\n",
        ],
    ],
)
async def test_invalid_or_unbounded_stream_fails_closed(blocks):
    client = client_for(Chunks(blocks))
    try:
        with pytest.raises(ModelStreamError) as caught:
            _ = [part async for part in client.stream_request(body(client))]
        assert caught.value.code == "invalid_stream" and caught.value.unknown
    finally:
        await client.close()


async def test_openai_usage_only_frame_and_missing_usage_are_distinct():
    for usage in (None, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}):
        blocks = [event({"content": "answer"}, "stop")]
        if usage is not None:
            blocks.append(
                b"data: " + json.dumps({"choices": [], "usage": usage}).encode() + b"\n\n"
            )
        blocks.append(b"data: [DONE]\n\n")
        client = client_for(Chunks(blocks))
        try:
            result = [part async for part in client.stream_request(body(client))]
            assert result[-1].finish == "stop"
            assert (result[-1].usage is None) == (usage is None)
        finally:
            await client.close()


async def test_truncated_tools_never_exposed_as_calls():
    client = client_for(
        Chunks(
            [
                event(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-1",
                                "function": {"name": "search_events", "arguments": '{"q":'},
                            }
                        ]
                    },
                    "length",
                ),
                b"data: [DONE]\n\n",
            ]
        )
    )
    try:
        result = [part async for part in client.stream_request(body(client))]
        assert result[-1].finish == "length" and result[-1].tools == ()
    finally:
        await client.close()


@pytest.mark.parametrize("status", [302, 401, 429, 500])
async def test_provider_errors_are_generic_and_never_retried(status):
    seen = []
    client = client_for(Chunks([b"private details"]), seen, status)
    try:
        with pytest.raises(ModelStreamError) as caught:
            _ = [part async for part in client.stream_request(body(client))]
        assert caught.value.code == "provider_rejected"
        assert "private" not in str(caught.value) and len(seen) == 1
    finally:
        await client.close()
