"""`patient_access` collection.

The MVP authorization grant. A doctor may only read a patient's profile,
documents and summary if a row exists here.

Design note: the grant is created by the PATIENT (consent), not by the
doctor. There is no "request access" workflow in the MVP -- that would be a
new feature, not a fix.
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


def serialize_access(access: PatientAccessDocument, patient_name: str = "") -> dict:
    return {
        "id": str(access["_id"]),
        "patient_id": access.get("patient_id"),
        "patient_name": patient_name,
        "status": access.get("status"),
        "granted_at": access.get("granted_at"),
        "revoked_at": access.get("revoked_at"),
        "note": access.get("note"),
    }
