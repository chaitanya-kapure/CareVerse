"""Patient profile read/update.

A profile row is created at registration (`AuthService.ensure_patient_profile`),
so this service normally just reads it. It re-creates the row if it is somehow
missing rather than failing the request, because the profile is a fixture of
having an account -- a patient who reaches this endpoint with no row should
see an empty form, not a 404.

Scope: plain contact details and the patient's own notes. Nothing in here
computes, infers or predicts anything about the patient.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database

from app.models.collections import get_patient_profiles, get_users
from app.models.patient_profile import PatientProfileDocument, serialize_profile
from app.schemas.profile import PatientProfileUpdate
from app.utils import errors

logger = logging.getLogger(__name__)

# Fields a PATCH is allowed to write. Kept as an explicit set rather than
# taken from `model_dump()` keys, so a future schema field cannot start
# writing to Mongo without being added here on purpose.
EDITABLE_FIELDS = (
    "full_name",
    "date_of_birth",
    "gender",
    "phone",
    "address",
    "notes",
)


class ProfileService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._profiles = get_patient_profiles(db)
        self._users = get_users(db)

    # --- read -------------------------------------------------------------

    def get(self, patient_id: str) -> dict:
        profile = self._profiles.find_one({"patient_id": patient_id})
        if profile is None:
            # Created lazily rather than raising: see the module docstring.
            profile = self._create(patient_id)
            if profile is None:
                raise errors.not_found("Profile not found", code="PROFILE_NOT_FOUND")
        return serialize_profile(profile)

    # --- write ------------------------------------------------------------

    def update(self, patient_id: str, payload: PatientProfileUpdate) -> dict:
        # `exclude_unset` is the whole point of the PATCH shape: a request
        # that only supplies `phone` must not blank every other field.
        changes = payload.model_dump(exclude_unset=True)

        if not changes:
            # Nothing to do. Returning the profile rather than a bare 200
            # keeps the client's flow to a single round trip.
            return self.get(patient_id)

        unknown = set(changes) - set(EDITABLE_FIELDS)
        if unknown:
            # Unreachable through Pydantic (extra fields are ignored), but a
            # guard against a future field being silently persisted.
            raise errors.bad_request(
                "Cannot update that field", code="PROFILE_FIELD_NOT_ALLOWED"
            )

        now = datetime.now(timezone.utc)
        changes["updated_at"] = now

        result = self._profiles.update_one(
            {"patient_id": patient_id}, {"$set": changes}
        )
        if result.matched_count == 0:
            self._create(patient_id)
            self._profiles.update_one(
                {"patient_id": patient_id}, {"$set": changes }
            )

        # `full_name` mirrors `users.name` so the name shown in the topbar
        # and the name on the profile cannot drift apart. They are one piece
        # of information to the patient; storing it twice only invites a
        # mismatch.
        if "full_name" in changes and changes["full_name"]:
            self._users.update_one(
                {"_id": ObjectId(patient_id)},
                {"$set": {"name": changes["full_name"], "updated_at": now}},
            )

        return self.get(patient_id)

    # --- helpers ----------------------------------------------------------

    def _create(self, patient_id: str) -> Optional[PatientProfileDocument]:
        """Insert the profile row if it does not exist yet.

        The caller must be a patient; a doctor reaching this path is refused
        by the route's role dependency before the service is ever constructed.
        """
        user = self._users.find_one({"_id": ObjectId(patient_id)})
        if user is None or user.get("role") != "patient":
            logger.warning("profile requested for a non-patient account")
            return None

        now = datetime.now(timezone.utc)
        document: PatientProfileDocument = {
            "patient_id": patient_id,
            "full_name": user.get("name", ""),
            "date_of_birth": None,
            "gender": "unspecified",
            "phone": None,
            "address": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
        }
        # `$setOnInsert` + upsert rather than a plain insert: two concurrent
        # requests must not create two profiles. The unique index on
        # patient_id is the real guard; this keeps the race quiet.
        self._profiles.update_one(
            {"patient_id": patient_id},
            {"$setOnInsert": document},
            upsert=True,
        )
        return self._profiles.find_one({"patient_id": patient_id})
