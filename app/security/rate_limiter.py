"""
In-memory sliding-window rate limiter for FastAPI (Phase 5 Security Hardening).
Provides per-IP and per-User request throttling on CPU/cost-heavy endpoints.
"""
import time
import threading
from typing import Dict, List, Optional, Tuple
from fastapi import Request, HTTPException, status
import logging

logger = logging.getLogger("ai_face_analyzer.security.rate_limiter")


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter.
    Tracks timestamps within a specified window in seconds.
    """
    def __init__(self, requests_per_window: int, window_seconds: int = 60, name: str = "default"):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.name = name
        self._history: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def _get_client_identifier(self, request: Request, custom_id: Optional[str] = None) -> str:
        if custom_id:
            return f"user:{custom_id}"
        
        # Check standard reverse proxy headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"
            
        return f"ip:{client_ip}"

    def check(self, request: Request, custom_id: Optional[str] = None) -> None:
        """
        Check and record request. Raises HTTPException(429) if limit exceeded.
        """
        key = self._get_client_identifier(request, custom_id)
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Clean old entries
            timestamps = self._history.get(key, [])
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= self.requests_per_window:
                # Calculate retry-after
                oldest = valid_timestamps[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                logger.warning(
                    f"Rate limit exceeded on [{self.name}] for {key}. "
                    f"Count: {len(valid_timestamps)}/{self.requests_per_window} in {self.window_seconds}s. "
                    f"Retry-After: {retry_after}s"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {self.name}. Maximum {self.requests_per_window} requests per {self.window_seconds}s.",
                    headers={"Retry-After": str(retry_after)}
                )

            valid_timestamps.append(now)
            self._history[key] = valid_timestamps

    def reset(self) -> None:
        """Reset history (useful for unit testing)."""
        with self._lock:
            self._history.clear()


# Default production limiters:
# Auth: 5 requests per 60 seconds (brute force protection)
auth_limiter = SlidingWindowRateLimiter(requests_per_window=5, window_seconds=60, name="auth")

# Scans/Analysis: 10 requests per 60 seconds (CPU / LLM cost protection)
scan_limiter = SlidingWindowRateLimiter(requests_per_window=10, window_seconds=60, name="scan")


def limit_auth_requests(request: Request) -> None:
    """FastAPI dependency for auth endpoint throttling."""
    auth_limiter.check(request)


def limit_scan_requests(request: Request) -> None:
    """FastAPI dependency for scan/analyze endpoint throttling."""
    # We can throttle by IP or token if Authorization header is present
    auth_header = request.headers.get("authorization", "")
    token_sub = None
    if auth_header.startswith("Bearer "):
        try:
            from app.auth.security import decode_token
            payload = decode_token(auth_header.split(" ", 1)[1])
            token_sub = payload.get("sub")
        except Exception:
            pass
    scan_limiter.check(request, custom_id=token_sub)
