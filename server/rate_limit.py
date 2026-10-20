"""Small in-process limiter for the AI endpoints.

The deployment is intentionally single-process for the proof of concept. A
host-level proxy should add distributed limits if the app is scaled out.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException

WINDOW_SECONDS = 60.0
MAX_REQUESTS_PER_WINDOW = 6
_LOCK = Lock()
_REQUESTS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def check_ai_rate_limit(owner: str, client_host: str, endpoint: str) -> None:
    now = monotonic()
    key = (f"{client_host}:{owner}", endpoint)
    with _LOCK:
        requests = _REQUESTS[key]
        while requests and now - requests[0] >= WINDOW_SECONDS:
            requests.popleft()
        if len(requests) >= MAX_REQUESTS_PER_WINDOW:
            retry_after = max(1, int(WINDOW_SECONDS - (now - requests[0])))
            raise HTTPException(
                status_code=429,
                detail="AI request limit reached. Try again in a minute.",
                headers={"Retry-After": str(retry_after)},
            )
        requests.append(now)


def clear_rate_limits() -> None:
    with _LOCK:
        _REQUESTS.clear()
