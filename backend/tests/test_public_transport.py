import ssl
from typing import Any

import httpcore
import httpx
import pytest

from radar.ingest.core import UnsafeUrl, canonicalize_url
from radar.ingest.public_transport import (
    PublicAsyncTransport,
    is_public_address,
)


class SslInfo:
    def selected_alpn_protocol(self) -> None:
        return None


class RecordingStream(httpcore.AsyncNetworkStream):
    def __init__(self) -> None:
        self.response = [b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"]
        self.writes: list[bytes] = []
        self.server_hostname: str | None = None

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self.response.pop(0) if self.response else b""

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.writes.append(buffer)

    async def aclose(self) -> None:
        return None

    async def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.AsyncNetworkStream:
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname is True
        self.server_hostname = server_hostname
        return self

    def get_extra_info(self, info: str) -> Any:
        return SslInfo() if info == "ssl_object" else None


class RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, error: Exception | None = None) -> None:
        self.connections: list[tuple[str, int]] = []
        self.stream = RecordingStream()
        self.error = error

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        self.connections.append((host, port))
        if self.error is not None:
            raise self.error
        return self.stream

    async def connect_unix_socket(self, path: str, timeout=None, socket_options=None):
        raise AssertionError("unix socket must not be used")


async def public_resolver(host: str) -> list[str]:
    assert host == "news.example"
    return ["93.184.216.34"]


@pytest.mark.asyncio
async def test_transport_connects_validated_ip_but_preserves_host_and_tls_name() -> None:
    backend = RecordingBackend()
    transport = PublicAsyncTransport(resolver=public_resolver, network_backend=backend)
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        response = await client.get("https://news.example/story")
        assert await response.aread() == b"ok"

    assert backend.connections == [("93.184.216.34", 443)]
    assert backend.stream.server_hostname == "news.example"
    request_bytes = b"".join(backend.stream.writes)
    assert b"Host: news.example" in request_bytes
    assert b"93.184.216.34" not in request_bytes


@pytest.mark.asyncio
async def test_mixed_public_private_dns_is_rejected_before_connect() -> None:
    backend = RecordingBackend()

    async def mixed_resolver(_host: str) -> list[str]:
        return ["93.184.216.34", "127.0.0.1"]

    transport = PublicAsyncTransport(resolver=mixed_resolver, network_backend=backend)
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        with pytest.raises(httpx.ConnectError, match="non-public"):
            await client.get("https://news.example/story")

    assert backend.connections == []


@pytest.mark.asyncio
async def test_httpcore_connect_timeout_maps_to_httpx() -> None:
    backend = RecordingBackend(httpcore.ConnectTimeout("late"))
    transport = PublicAsyncTransport(resolver=public_resolver, network_backend=backend)
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        with pytest.raises(httpx.ConnectTimeout):
            await client.get("https://news.example/story")


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.1.1", "::1", "::ffff:8.8.8.8"],
)
def test_non_public_and_ipv4_mapped_addresses_are_rejected(address: str) -> None:
    assert is_public_address(address) is False


@pytest.mark.parametrize(
    "url",
    ["https://user@news.example/x", "https://user:secret@news.example/x"],
)
def test_url_userinfo_is_rejected(url: str) -> None:
    with pytest.raises(UnsafeUrl, match="userinfo"):
        canonicalize_url(url)
