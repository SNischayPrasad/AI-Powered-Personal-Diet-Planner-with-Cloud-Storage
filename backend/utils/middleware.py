"""Request middleware: tracing, access logs, metrics, security headers and a safety net.

For every request it:
1. assigns a request ID (or accepts a well-formed ``X-Request-ID`` from a load balancer),
2. converts any unexpected exception into a generic JSON 500 (no stack traces leak),
3. adds security headers,
4. counts the request in the metrics and writes one access-log line.
"""

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from starlette.responses import Response

from backend.utils.errors import error_response
from backend.utils.logging_config import request_id_ctx

logger = logging.getLogger("diet_planner.http")

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_DOCS_PATHS = ("/api/docs", "/api/redoc")

BASE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# JSON API responses never need to load scripts, styles or frames.
API_ONLY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",  # responses contain private user data
}


def _route_label(request: Request) -> str:
    """Use the route *template* (/api/plans/{plan_id}) — not the raw path — so metrics
    don't explode into one series per ID."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def _apply_security_headers(request: Request, response: Response, *, hsts: bool) -> None:
    for name, value in BASE_SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(_DOCS_PATHS):
        for name, value in API_ONLY_HEADERS.items():
            response.headers.setdefault(name, value)
    if hsts:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )


def register_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        incoming_id = request.headers.get("X-Request-ID", "")
        request_id = incoming_id if _SAFE_REQUEST_ID.match(incoming_id) else uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        context_token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("Unhandled error while processing %s %s",
                                 request.method, request.url.path)
                response = error_response(
                    request, 500, "internal_error", "Something went wrong. Please try again."
                )

            duration_ms = (time.perf_counter() - started) * 1000
            response.headers["X-Request-ID"] = request_id
            _apply_security_headers(
                request, response, hsts=request.app.state.settings.is_production
            )
            route = _route_label(request)
            request.app.state.metrics.inc(
                "http_requests_total",
                method=request.method,
                route=route,
                status=str(response.status_code),
            )
            logger.info(
                "%s %s -> %s (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={
                    "method": request.method,
                    "route": route,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 1),
                },
            )
            return response
        finally:
            request_id_ctx.reset(context_token)
