"""`patient_access` collection.

The MVP authorization grant. A doctor may only read a patient's profile,
documents and summary if a row exists here.

Design note: the grant is created by the PATIENT (consent), not by the
doctor. There is no "request access" workflow in the MVP -- that would be a
new feature, not a fix.

Scope note: this is the whole authorization model. There is no organization,
no role hierarchy, no per-field permission and no invitation state machine.
One row means one doctor may read one patient's records, and its absence
means they may not. Everything downstream -- `assert_patient_access` and
every doctor route -- reads this one collection, so there is no second
place to get the answer wrong.
"""

from datetime import datetime
from typing import Literal, Optional, TypedDict

AccessStatus = Literal["active", "revoked"]


class PatientAccessDocument(TypedDict, total=False):
    _id: object
    patient_id: str                    # -> users._id (role=patient)
    doctor_id: str                     # -> users._id (role=doctor)
    status: AccessStatus               # "revoked" rows are kept as an audit trail
    granted_at: datetime
    revoked_at: Optional[datetime]
    # Free-text reason the patient gave when granting. Optional.
    note: Optional[str]


def serialize_access(access: PatientAccessDocument, doctor_name: str = "") -> dict:
    """Response shape for a grant.

    Carries the doctor's display name so the patient can recognise who they
    authorized, and never the doctor's account details -- a patient authorizing
    a doctor needs to know *which* doctor, not that doctor's email or password
    material.
    """
    return {
        "id": str(access["_id"]),
        "patient_id": access.get("patient_id"),
        "doctor_id": access.get("doctor_id"),
        "doctor_name": doctor_name,
        "status": access.get("status"),
        "granted_at": access.get("granted_at"),
        "revoked_at": access.get("revoked_at"),
        "note": access.get("note"),
    }


# One live grant per doctor/patient pair. Enforced in the database rather than
# by a read-then-write in the service, because two concurrent grant requests
# would otherwise both pass the check and both insert.
#
# Partial on `status: "active"` so that a revoked row can be kept for the
# audit trail while a fresh grant for the same doctor can be issued later --
# a plain unique index over (doctor_id, patient_id) would make re-granting
# impossible after a single revoke.
UNIQUE_ACTIVE_GRANT_KEYS = [("doctor_id", 1), ("patient_id", 1)]
UNIQUE_ACTIVE_GRANT_FILTER = {"status": "active"}
UNIQUE_ACTIVE_GRANT_INDEX = "uniq_active_doctor_patient"
