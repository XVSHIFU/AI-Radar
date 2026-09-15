"""Small, bounded admission control for the single-process public answer API."""

from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from time import monotonic


class AskLimitReached(RuntimeError):
    pass


class AskAdmission:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        max_active: int = 2,
        per_client: int = 6,
        total_per_minute: int = 30,
        max_clients: int = 1024,
    ) -> None:
        self._clock = clock
        self._max_active = max_active
        self._per_client = per_client
        self._total_per_minute = total_per_minute
        self._max_clients = max_clients
        self._active = 0
        self._clients: dict[str, deque[float]] = {}
        self._recent: deque[float] = deque()

    @contextmanager
    def slot(self, client: str) -> Iterator[None]:
        now = self._clock()
        cutoff = now - 60
        for key, timestamps in list(self._clients.items()):
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                del self._clients[key]
        while self._recent and self._recent[0] <= cutoff:
            self._recent.popleft()
        if self._active >= self._max_active or len(self._recent) >= self._total_per_minute:
            raise AskLimitReached("回答请求较多，请稍后重试。")
        if client not in self._clients and len(self._clients) >= self._max_clients:
            raise AskLimitReached("回答请求较多，请稍后重试。")
        times = self._clients.get(client)
        if times is not None and len(times) >= self._per_client:
            raise AskLimitReached("提问过于频繁，请稍后重试。")
        if times is None:
            times = self._clients.setdefault(client, deque())
        times.append(now)
        self._recent.append(now)
        self._active += 1
        try:
            yield
        finally:
            self._active -= 1
