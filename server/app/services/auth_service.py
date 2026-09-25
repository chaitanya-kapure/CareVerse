"""Authentication business logic.

Split out of the router so it can be called from the seed script or a test
without going through HTTP.
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.collections import get_users
from app.models.user import UserDocument, serialize_user
from app.schemas.auth import RegisterRequest
from app.utils import errors
from app.utils.security import hash_password, verify_password


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._users = get_users(db)

    def register(self, payload: RegisterRequest) -> dict:
        email = normalize_email(payload.email)

        if self._users.find_one({"email": email}):
            raise errors.conflict("Email already registered", code="EMAIL_TAKEN")

        now = datetime.now(timezone.utc)
        document: UserDocument = {
            "name": payload.name.strip(),
            "email": email,
            "password_hash": hash_password(payload.password),
            "role": payload.role,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = self._users.insert_one(document)
        except DuplicateKeyError:
            # Lost a race against a concurrent registration for the same
            # address. The unique index is the real guard; this pre-check is
            # only a friendlier fast path.
            raise errors.conflict("Email already registered", code="EMAIL_TAKEN")

        document["_id"] = result.inserted_id
        return serialize_user(document)

    def authenticate(self, email: str, password: str) -> Optional[UserDocument]:
        """Return the user document when the credentials are valid."""
        user = self._users.find_one({"email": normalize_email(email)})
        if user is None:
            # Hash a throwaway value so that a missing account and a wrong
            # password take a similar amount of time, which keeps the
            # endpoint from confirming which emails are registered.
            verify_password(password, hash_password("timing-equalizer"))
            return None
        if not verify_password(password, user.get("password_hash", "")):
            return None
        return user

    def get_by_id(self, user_id) -> Optional[UserDocument]:
        if not ObjectId.is_valid(str(user_id)):
            return None
        return self._users.find_one({"_id": ObjectId(str(user_id))})

    def ensure_patient_profile(self, user_id: str) -> None:
        """Created here so a patient always has a profile to upload into.

        Uses upsert + return_document so that a patient re-registering never
        ends up with two profiles.
        """
        from app.models.collections import get_patient_profiles

        user = self.get_by_id(user_id)
        if user is None or user.get("role") != "patient":
            return

        now = datetime.now(timezone.utc)
        get_patient_profiles(self._db).update_one(
            {"patient_id": user_id},
            {
                "$setOnInsert": {
                    "patient_id": user_id,
                    "full_name": user.get("name", ""),
                    "date_of_birth": None,
                    "gender": "unspecified",
                    "phone": None,
                    "address": None,
                    "notes": None,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
