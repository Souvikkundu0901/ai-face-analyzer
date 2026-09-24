"""
FastAPI Request Logging and Tracing Middleware (Phase 5 Monitoring).
Generates X-Request-ID for every request and logs latency and status codes.
"""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.monitoring.metrics import metrics

logger = logging.getLogger("ai_face_analyzer.access")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = req_id
        
        start_time = time.perf_counter()
        
        # Get client IP safely
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"[{req_id}] {request.method} {request.url.path} -> 500 Unhandled Exception in {duration_ms:.1f}ms (IP: {client_ip}) | {exc}"
            )
            metrics.record_http_request(500)
            raise exc

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = req_id
        
        # Record metrics
        metrics.record_http_request(response.status_code)
        
        # Don't clutter logs for static assets or health poll unless non-200
        is_quiet = request.url.path.startswith("/static/") or request.url.path == "/favicon.ico"
        if not is_quiet:
            log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
            logger.log(
                log_level,
                f"[{req_id}] {request.method} {request.url.path} -> {response.status_code} in {duration_ms:.1f}ms (IP: {client_ip})"
            )

        return response
