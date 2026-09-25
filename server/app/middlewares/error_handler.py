"""Global error handling.

Normalizes every failure into `{"detail": ..., "code": ...}` so the client
has exactly one error shape to parse. FastAPI's own validation errors are
translated too, otherwise the client would need a second parser.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.errors import build_error_body

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code = None
        if exc.headers:
            code = exc.headers.get("code")
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_body(str(exc.detail), code),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Flatten pydantic's error list into one sentence the UI can show
        # above the form. The full list stays on the server log.
        problems = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            message = error.get("msg", "Invalid value")
            problems.append(f"{location}: {message}" if location else message)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error_body("; ".join(problems) or "Invalid request", "VALIDATION_ERROR"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Never leak a stack trace or a database string to the client; a
        # health-records API should not leak internals on unexpected errors.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=build_error_body("An unexpected error occurred", "INTERNAL_ERROR"),
        )
