"""Shared error helpers and the standard error envelope.

Every failure the API returns looks the same:

    {"detail": "<human readable>", "code": "<MACHINE_CODE>"}

`detail` is kept for backwards compatibility with the existing client, which
already reads it.
"""

from typing import Any, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError


def unauthorized(detail: str = "Invalid or expired token", code: str = "UNAUTHORIZED"):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"code": code, "WWW-Authenticate": "Bearer"},
    )


def forbidden(detail: str = "You do not have access to this resource", code: str = "FORBIDDEN"):
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
        headers={"code": code},
    )


def not_found(detail: str = "Resource not found", code: str = "NOT_FOUND"):
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
        headers={"code": code},
    )


def conflict(detail: str, code: str = "CONFLICT"):
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
        headers={"code": code},
    )


def bad_request(detail: str, code: str = "BAD_REQUEST"):
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
        headers={"code": code},
    )


def unprocessable(detail: str, code: str = "UNPROCESSABLE"):
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=detail,
        headers={"code": code},
    )


# Added for the document upload path. Both are real HTTP semantics rather
# than a 400 with a nicer message: 413 says "this will never be accepted as
# sized" and 415 says "no content type of yours will ever be accepted", and
# the client can branch on `code` without parsing prose.


def payload_too_large(detail: str, code: str = "PAYLOAD_TOO_LARGE"):
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=detail,
        headers={"code": code},
    )


def unsupported_media_type(detail: str, code: str = "UNSUPPORTED_MEDIA_TYPE"):
    return HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=detail,
        headers={"code": code},
    )


def server_error(detail: str, code: str = "INTERNAL_ERROR"):
    """A 500 that is allowed to say something useful.

    The global unhandled-exception handler answers with a generic sentence,
    which is the right default for an unexpected crash. A storage failure is
    *expected* and diagnosed, so it can safely tell the patient what failed
    and carry a specific `code` -- while still revealing nothing about the
    server, the path, or the exception type.
    """
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
        headers={"code": code},
    )


def flatten_errors(raw_errors: list) -> str:
    """Collapse Pydantic's error list into one sentence the UI can show.

    Shared by the global `RequestValidationError` handler and by handlers
    that build a body themselves, so both failure paths read the same to the
    client. The full detail stays on the server log.
    """
    problems: list[str] = []
    for error in raw_errors:
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        message = error.get("msg", "Invalid value")
        problems.append(f"{location}: {message}" if location else message)
    return "; ".join(problems) or "Invalid request"


def from_pydantic(exc: ValidationError) -> HTTPException:
    """Convert a Pydantic `ValidationError` raised inside a handler into 422.

    FastAPI only translates `ValidationError` into a 422 automatically for
    parameters it declared itself. A body built by hand inside a handler --
    the multipart upload fields, for example -- would otherwise surface as an
    unhandled 500 and show the patient "An unexpected error occurred" for a
    mistyped date.
    """
    return unprocessable(flatten_errors(exc.errors()), "VALIDATION_ERROR")


def build_error_body(detail: str, code: Optional[str] = None) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": detail}
    if code:
        body["code"] = code
    return body
