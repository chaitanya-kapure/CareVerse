"""Doctor <-> patient authorization grants.

This is the only module in the project that writes to `patient_access`. The
doctor read routes never create or modify a grant; they only ask
`assert_patient_access` whether one exists. Keeping creation in one place is
what makes "who can see this patient" a single question with a single answer.

Scope, deliberately small:

  * A grant names one doctor and one patient. No organizations, no roles
    beyond the two account types, no per-field permissions.
  * The patient grants; the doctor never requests. There is no invitation or
    approval state machine, because a request flow would mean a doctor could
    *ask* for a patient's records, and the security model here is that access
    only ever originates from the patient.
  * Revocation sets `status` rather than deleting the row, so "who had access
    to this record last March" stays answerable.

The uniqueness of a live grant is enforced by a partial unique index
(`models/access.py`), not by the read-then-write below. A pre-check here is
only a friendlier failure for the common case; the index is the real guard.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.access import (
    PatientAccessDocument,
    serialize_access,
)
from app.models.collections import get_patient_access, get_users
from app.models.user import UserDocument
from app.utils import errors

logger = logging.getLogger(__name__)

# A note is the patient's own words about why they shared. It is a sentence to
# their doctor, not a field, so it is kept short and is never interpreted.
MAX_NOTE_LENGTH = 500


class AccessService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._access = get_patient_access(db)
        self._users = get_users(db)

    # ==================================================================
    # patient side
    # ==================================================================

    def list_for_patient(self, patient_id: str) -> list[dict]:
        """Every grant this patient has issued, newest first.

        Includes revoked rows on purpose: a patient who revoked a doctor is
        entitled to see that they did, and the revocation date is the evidence.
        """
        rows = list(
            self._access.find({"patient_id": patient_id}).sort("granted_at", -1)
        )
        return [self._serialize_with_doctor_name(row) for row in rows]

    def grant(
        self, patient_id: str, doctor_id: str, note: Optional[str] = None
    ) -> dict:
        """Authorize one doctor to read one patient's records.

        Called only on behalf of the patient themself (the route carries no
        doctor id from the client other than the one being authorized), so
        this is a patient consenting, not a doctor self-appointing.
        """
        doctor = self._require_doctor(doctor_id)
        if str(doctor["_id"]) == patient_id:
            # Only reachable if an account were both roles. Refused rather
            # than allowed to read its own records through the doctor path,
            # which would sidestep every owner check in the patient routes.
            raise errors.bad_request(
                "This account cannot be authorized against itself.",
                code="SELF_ACCESS_NOT_ALLOWED",
            )

        now = datetime.now(timezone.utc)
        document: PatientAccessDocument = {
            "patient_id": patient_id,
            "doctor_id": str(doctor["_id"]),
            "status": "active",
            "granted_at": now,
            "revoked_at": None,
            "note": (note or "").strip() or None,
        }

        try:
            self._access.insert_one(document)
        except DuplicateKeyError:
            # The partial unique index refused a second live grant for this
            # pair. Answering with the same code a first grant would have used
            # keeps the repeat from looking like a different kind of failure.
            raise errors.conflict(
                "That doctor already has access to your records.",
                code="ACCESS_ALREADY_GRANTED",
            )

        # pymongo writes the generated `_id` back into the document it was
        # given, so the row we return is the row that was actually stored.
        return self._serialize_with_doctor_name(document)

    def revoke(self, patient_id: str, access_id: str) -> dict:
        """End one grant. The row is kept, marked revoked."""
        if not ObjectId.is_valid(access_id):
            # Same 404 as an id belonging to somebody else: a malformed id
            # must not be distinguishable from a valid one the patient does
            # not own, or the endpoint becomes a probe for what exists.
            raise errors.not_found("Grant not found", code="ACCESS_NOT_FOUND")

        # `patient_id` is inside the filter, so another patient's grant id is
        # simply not found rather than forbidden.
        result = self._access.update_one(
            {
                "_id": ObjectId(access_id),
                "patient_id": patient_id,
                "status": "active",
            },
            {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc)}},
        )
        if result.matched_count == 0:
            raise errors.not_found("Grant not found", code="ACCESS_NOT_FOUND")

        row = self._access.find_one({"_id": ObjectId(access_id)})
        return self._serialize_with_doctor_name(row)

    # ==================================================================
    # doctor side
    # ==================================================================

    def list_authorized_patient_ids(self, doctor_id: str) -> list[str]:
        """The patient ids this doctor may read, newest grant first.

        Authorization is expressed as a set rather than a check so the list
        screen cannot accidentally become a way to *test* ids: the doctor is
        shown what they already have, never asked whether a given id is theirs.
        """
        cursor = self._access.find(
            {"doctor_id": doctor_id, "status": "active"}
        ).sort("granted_at", -1)
        return [row["patient_id"] for row in cursor if row.get("patient_id")]

    # ==================================================================
    # helpers
    # ==================================================================

    def _require_doctor(self, doctor_id: str) -> UserDocument:
        """Resolve a doctor id, or refuse it.

        The target must exist *and* be a doctor. Validating the role here means
        a grant can never be attached to a patient account, which would
        otherwise let one patient read another's records.
        """
        if not ObjectId.is_valid(doctor_id or ""):
            raise errors.not_found("Doctor not found", code="DOCTOR_NOT_FOUND")

        user = self._users.find_one({"_id": ObjectId(doctor_id)})
        if user is None or user.get("role") != "doctor":
            # One answer for "no such doctor" and "that is not a doctor": the
            # difference is not the caller's business, and a patient granting
            # access is not an attacker enumerating staff accounts.
            raise errors.not_found("Doctor not found", code="DOCTOR_NOT_FOUND")
        return user

    def _serialize_with_doctor_name(self, row: PatientAccessDocument) -> dict:
        doctor_id = row.get("doctor_id")
        doctor = (
            self._users.find_one({"_id": ObjectId(doctor_id)}) if doctor_id else None
        )
        return serialize_access(row, doctor.get("name", "") if doctor else "")
