"""access_requests collection — doctor-initiated, patient-approved workflow."""
from datetime import datetime
from typing import Literal, Optional, TypedDict

AccessRequestStatus = Literal["pending", "approved", "rejected", "revoked", "expired"]


class AccessRequestDocument(TypedDict, total=False):
    _id: object
    doctor_id: str
    doctor_name: str
    patient_careverse_id: str   # the 4-digit ID entered by doctor
    patient_id: str             # resolved user._id
    purpose: str
    requested_categories: list  # list[str]
    requested_duration_days: int
    status: AccessRequestStatus
    rejection_reason: Optional[str]
    grant_id: Optional[str]     # -> patient_access._id when approved
    created_at: datetime
    responded_at: Optional[datetime]


def serialize_access_request(req: AccessRequestDocument) -> dict:
    return {
        "id": str(req["_id"]),
        "doctor_id": req.get("doctor_id"),
        "doctor_name": req.get("doctor_name", ""),
        "patient_careverse_id": req.get("patient_careverse_id"),
        "patient_id": req.get("patient_id"),
        "purpose": req.get("purpose", ""),
        "requested_categories": req.get("requested_categories") or [],
        "requested_duration_days": req.get("requested_duration_days", 30),
        "status": req.get("status", "pending"),
        "rejection_reason": req.get("rejection_reason"),
        "grant_id": req.get("grant_id"),
        "created_at": req.get("created_at"),
        "responded_at": req.get("responded_at"),
    }
