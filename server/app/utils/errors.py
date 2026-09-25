"""Shared error helpers and the standard error envelope.

Every failure the API returns looks the same:

    {"detail": "<human readable>", "code": "<MACHINE_CODE>"}

`detail` is kept for backwards compatibility with the existing client, which
already reads it.
"""

from typing import Any, Optional

from fastapi import HTTPException, status


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


def build_error_body(detail: str, code: Optional[str] = None) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": detail}
    if code:
        body["code"] = code
    return body
