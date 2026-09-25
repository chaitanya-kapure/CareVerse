"""`users` collection.

One document per account. The only two roles are `patient` and `doctor`.
"""

from datetime import datetime
from typing import Literal, Optional, TypedDict

UserRole = Literal["patient", "doctor"]
UserStatus = Literal["active", "disabled"]


class UserDocument(TypedDict, total=False):
    _id: object
    name: str
    email: str                 # stored lowercased, unique
    password_hash: str         # bcrypt, never selected into a response
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


def serialize_user(user: UserDocument) -> dict:
    """Public shape of a user. Deliberately omits `password_hash`."""
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role"),
    }


def user_display_name(user: Optional[UserDocument]) -> str:
    if not user:
        return "Unknown"
    return user.get("name") or user.get("email", "Unknown")
