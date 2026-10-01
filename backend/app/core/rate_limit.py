from collections import deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._entries: dict[str, deque[float]] = {}
        self._lock = Lock()

    def is_limited(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = monotonic()
        threshold = now - window_seconds

        with self._lock:
            bucket = self._entries.setdefault(key, deque())
            while bucket and bucket[0] <= threshold:
                bucket.popleft()

            if len(bucket) >= max_requests:
                return True

            bucket.append(now)
            return False

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


def request_client_fingerprint(x_forwarded_for: str | None, client_host: str | None) -> str:
    if x_forwarded_for:
        first_hop = x_forwarded_for.split(",", maxsplit=1)[0].strip()
        if first_hop:
            return first_hop
    return client_host or "unknown"
