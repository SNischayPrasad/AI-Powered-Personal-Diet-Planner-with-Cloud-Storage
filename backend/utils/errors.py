"""Consistent, safe error responses.

Every error the API returns has the same JSON shape, which makes the frontend simpler and
never leaks stack traces or internal details:

    {"error": {"code": "not_found", "message": "Plan not found.", "request_id": "1f3a…"}}

The ``request_id`` is also written to the server logs, so a user-visible error can be traced
to the exact log lines that explain it.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("diet_planner.errors")


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    status_code = 500
    code = "internal_error"
    message = "Something went wrong. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
        details: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.headers = headers
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "The request could not be processed."


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"
    message = "Authentication required."

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kwargs)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "The resource already exists."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"
    message = "The uploaded file is too large."


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "unsupported_media_type"
    message = "This file type is not supported."


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"
    message = "The request is valid but cannot be fulfilled."


class RateLimitExceededError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please wait a moment and try again."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "A cloud service is temporarily unavailable. Please try again shortly."


def request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {"code": code, "message": message, "request_id": request_id_of(request)}
    }
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers=headers)


_HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            request, exc.status_code, exc.code, exc.message, details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        if exc.status_code == 404:
            message = "The requested resource was not found."
        return error_response(
            request, exc.status_code, code, message, headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"] if part != "body"),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        first = details[0] if details else None
        message = (
            f"Invalid value for '{first['field']}': {first['message']}"
            if first and first["field"]
            else "The request contains invalid data."
        )
        return error_response(request, 422, "validation_error", message, details=details)
