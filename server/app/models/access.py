"""`patient_access` collection."""

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
    """Response shape for a grant."""
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
UNIQUE_ACTIVE_GRANT_KEYS = [("doctor_id", 1), ("patient_id", 1)]
UNIQUE_ACTIVE_GRANT_FILTER = {"status": "active"}
UNIQUE_ACTIVE_GRANT_INDEX = "uniq_active_doctor_patient"
