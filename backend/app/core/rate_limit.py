"""Small per-process rate guard for a single-instance demo deployment."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

_windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()


def reset_rate_limits() -> None:
    """Clear counters for isolated tests."""
    with _lock:
        _windows.clear()


async def rate_limit_middleware(request: Request, call_next):
    settings = get_settings()
    if not settings.rate_limit_enabled or request.method == "OPTIONS" or not request.url.path.startswith("/api/v1/"):
        return await call_next(request)
    path = request.url.path
    if request.method == "POST" and path == "/api/v1/analyses":
        category, limit = "upload", settings.rate_limit_upload_per_minute
    elif request.method == "POST" and any(path.endswith(suffix) for suffix in ("/run", "/retrieve", "/verify", "/match", "/ocr/vision-retry")):
        category, limit = "processing", settings.rate_limit_processing_per_minute
    else:
        category, limit = "general", settings.rate_limit_general_per_minute
    client = request.client.host if request.client else "unknown"
    now = monotonic()
    with _lock:
        if len(_windows) > 10_000:
            for key in list(_windows):
                if not _windows[key] or _windows[key][-1] <= now - 60:
                    del _windows[key]
        if len(_windows) >= 10_000 and (client, category) not in _windows:
            return JSONResponse(status_code=503, content={"code": "UNAVAILABLE", "detail": "Service is busy. Try again shortly."})
        window = _windows[(client, category)]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= limit:
            retry_after = max(1, int(60 - (now - window[0]) + 0.999))
            return JSONResponse(status_code=429, headers={"Retry-After": str(retry_after)}, content={"code": "RATE_LIMITED", "detail": "Too many requests. Try again shortly."})
        window.append(now)
    return await call_next(request)
