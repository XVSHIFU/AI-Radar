import httpx
import pytest

from radar.ingest.dns import cloudflare_resolver, configured_resolver


@pytest.mark.parametrize("address", ["127.0.0.1", "198.18.0.1", "::1", "169.254.169.254"])
async def test_doh_rejects_private_literals(address):
    with pytest.raises(ValueError):
        await cloudflare_resolver(address)


async def test_doh_validates_answers_and_uses_fixed_endpoint(monkeypatch):
    requests = []

    async def handler(request):
        requests.append(request)
        answers = (
            [{"type": 1, "data": "93.184.216.34"}] if request.url.params["type"] == "A" else []
        )
        return httpx.Response(200, json={"Status": 0, "Answer": answers})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(
            **kw,
            transport=httpx.MockTransport(handler),
        ),
    )
    assert await cloudflare_resolver("example.org") == ["93.184.216.34"]
    assert len(requests) == 2
    assert all(r.url.host == "cloudflare-dns.com" for r in requests)


async def test_doh_rejects_mixed_public_private_answers(monkeypatch):
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "Status": 0,
                "Answer": [
                    {"type": 1, "data": "93.184.216.34"},
                    {"type": 1, "data": "10.0.0.1"},
                ],
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(
            **kw,
            transport=httpx.MockTransport(handler),
        ),
    )
    with pytest.raises(ValueError, match="non-public"):
        await cloudflare_resolver("example.org")


def test_unknown_dns_mode_fails_closed():
    with pytest.raises(ValueError):
        configured_resolver("automatic-bypass")
