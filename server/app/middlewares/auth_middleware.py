"""Authentication and authorization dependencies.

This is the security boundary for CAREVERSE. The rules it enforces:

  * A patient may read/write ONLY documents that belong to them.
  * A doctor may read ONLY patients that have granted them access.
  * Role alone never grants record access.

Frontend route guards are a UX convenience only. Every rule below is
re-checked here on the server, because the client can be bypassed.
"""

from typing import Annotated, Literal

from bson import ObjectId
from fastapi import Depends, Request
from pymongo.database import Database

from app.database import get_db
from app.models.collections import get_patient_access, get_users
from app.models.user import UserDocument, UserRole
from app.utils import errors
from app.utils.security import decode_access_token

DbDep = Annotated[Database, Depends(get_db)]

# How the caller reached this patient's data. Useful for audit logging and
# for showing "you are viewing your own record" in the UI.
OWNER = "owner"
GRANTED = "granted"

# Literal alias so the return type of assert_patient_access is self-documenting.
AccessMode = Literal["owner", "granted"]


def get_token_payload(request: Request) -> dict:
    """Validate the bearer token. Deliberately does NOT touch the database.

    Splitting this out of `get_current_user` fixes the dependency order:
    FastAPI resolves dependencies before calling a handler, so a single
    combined dependency would raise 503 (database down) before ever
    checking the token. Authenticating first means an invalid or missing
    token is a 401 regardless of database state, and an unauthenticated
    caller cannot probe whether the database is up.
    """
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise errors.unauthorized("Authentication required", code="MISSING_TOKEN")

    payload = decode_access_token(token)
    if payload is None:
        raise errors.unauthorized("Invalid or expired token", code="INVALID_TOKEN")

    subject = payload.get("sub")
    if not subject or not ObjectId.is_valid(subject):
        raise errors.unauthorized("Invalid token payload", code="INVALID_TOKEN_PAYLOAD")

    return payload


TokenPayload = Annotated[dict, Depends(get_token_payload)]


def get_current_user(payload: TokenPayload, db: DbDep) -> UserDocument:
    """Resolve a validated token into a live user document.

    The user is re-read from the database on every request rather than
    trusted from the token payload, so a disabled account or a changed role
    takes effect immediately instead of when the token expires.
    """
    user = get_users(db).find_one({"_id": ObjectId(payload["sub"])})
    if user is None:
        raise errors.unauthorized("User not found", code="USER_NOT_FOUND")

    if user.get("status") == "disabled":
        raise errors.forbidden("This account has been disabled", code="ACCOUNT_DISABLED")

    return user


CurrentUser = Annotated[UserDocument, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """Dependency factory: `user = Depends(require_roles("doctor"))`."""

    allowed = set(roles)

    def _dependency(user: CurrentUser) -> UserDocument:
        if user.get("role") not in allowed:
            raise errors.forbidden(
                f"This action requires the {' or '.join(sorted(allowed))} role",
                code="ROLE_NOT_ALLOWED",
            )
        return user

    return _dependency


def resolve_patient_id(raw_id: str) -> str:
    """Normalize a patient identifier, rejecting anything malformed early."""
    if not raw_id or not ObjectId.is_valid(raw_id):
        raise errors.bad_request("Invalid patient id", code="INVALID_PATIENT_ID")
    return raw_id


def assert_patient_access(
    db: Database,
    user: UserDocument,
    patient_id: str,
) -> AccessMode:
    """Return OWNER or GRANTED, or raise 403.

    The single place where "may this caller see this patient?" is decided.
    Both the patient routes and the doctor routes call it, so there is exactly
    one rule to audit.
    """
    role = user.get("role")
    caller_id = str(user["_id"])

    if role == "patient":
        # Ownership is the only accepted proof for a patient. Comparing the
        # string forms of the ids avoids ObjectId/string mismatches.
        if patient_id != caller_id:
            # Deliberately 403, not 404: the route already proved the patient
            # record exists, and the response shape must not vary by owner.
            raise errors.forbidden(
                "You can only access your own records", code="NOT_RECORD_OWNER"
            )
        return OWNER

    if role == "doctor":
        grant = get_patient_access(db).find_one(
            {
                "doctor_id": caller_id,
                "patient_id": patient_id,
                "status": "active",
            }
        )
        if grant is None:
            raise errors.forbidden(
                "You have not been granted access to this patient's records",
                code="NO_PATIENT_ACCESS",
            )
        return GRANTED

    # Unreachable while only two roles exist, but a new role must not
    # silently fall through into an unrestricted grant.
    raise errors.forbidden("Unsupported role", code="ROLE_NOT_ALLOWED")
