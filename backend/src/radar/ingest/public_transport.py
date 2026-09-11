from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable

import httpcore
import httpx

Resolver = Callable[[str], Awaitable[list[str]]]
SocketOption = (
    tuple[int, int, int] | tuple[int, int, bytes | bytearray] | tuple[int, int, None, int]
)


def is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return False
    return address.is_global and not address.is_multicast


async def system_resolver(host: str) -> list[str]:
    records = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    return sorted({str(record[4][0]) for record in records})


class PublicAsyncNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self,
        *,
        resolver: Resolver = system_resolver,
        backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self.resolver = resolver
        self.backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[SocketOption] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            addresses = await self.resolver(host)
        except (OSError, UnicodeError) as exc:
            raise httpcore.ConnectError(str(exc)) from exc
        if not addresses:
            raise httpcore.ConnectError(f"DNS returned no addresses for {host}")
        try:
            allowed = all(is_public_address(value) for value in addresses)
        except ValueError as exc:
            raise httpcore.ConnectError(f"DNS returned an invalid address for {host}") from exc
        if not allowed:
            raise httpcore.ConnectError(f"DNS returned a non-public address for {host}")
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for address in addresses:
            try:
                return await self.backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[SocketOption] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise httpcore.UnsupportedProtocol("Unix sockets are disabled for public fetching")


_EXCEPTION_MAP: tuple[tuple[type[Exception], type[httpx.HTTPError]], ...] = (
    (httpcore.ConnectTimeout, httpx.ConnectTimeout),
    (httpcore.ReadTimeout, httpx.ReadTimeout),
    (httpcore.WriteTimeout, httpx.WriteTimeout),
    (httpcore.PoolTimeout, httpx.PoolTimeout),
    (httpcore.ConnectError, httpx.ConnectError),
    (httpcore.ReadError, httpx.ReadError),
    (httpcore.WriteError, httpx.WriteError),
    (httpcore.ProxyError, httpx.ProxyError),
    (httpcore.LocalProtocolError, httpx.LocalProtocolError),
    (httpcore.RemoteProtocolError, httpx.RemoteProtocolError),
    (httpcore.UnsupportedProtocol, httpx.UnsupportedProtocol),
)
_HTTPCORE_ERRORS = tuple(source for source, _target in _EXCEPTION_MAP)


def map_httpcore_exception(exc: Exception, request: httpx.Request) -> httpx.HTTPError:
    for source, target in _EXCEPTION_MAP:
        if isinstance(exc, source):
            return target(str(exc), request=request)  # type: ignore[call-arg]
    return httpx.TransportError(str(exc), request=request)


class CoreResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream: AsyncIterator[bytes], request: httpx.Request) -> None:
        self.stream = stream
        self.request = request

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for part in self.stream:
                yield part
        except _HTTPCORE_ERRORS as exc:
            raise map_httpcore_exception(exc, self.request) from exc

    async def aclose(self) -> None:
        close = getattr(self.stream, "aclose", None)
        if close is not None:
            try:
                await close()
            except _HTTPCORE_ERRORS as exc:
                raise map_httpcore_exception(exc, self.request) from exc


class PublicAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        *,
        resolver: Resolver = system_resolver,
        network_backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        backend = PublicAsyncNetworkBackend(resolver=resolver, backend=network_backend)
        self.pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=backend,
            http1=True,
            http2=False,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        try:
            response = await self.pool.handle_async_request(core_request)
        except _HTTPCORE_ERRORS as exc:
            raise map_httpcore_exception(exc, request) from exc
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=CoreResponseStream(response.stream, request),  # type: ignore[arg-type]
            extensions=response.extensions,
        )

    async def aclose(self) -> None:
        await self.pool.aclose()
