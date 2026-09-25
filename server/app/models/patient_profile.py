"""`patient_profiles` collection.

Exactly one profile per patient user. This is the centralized record that
doctors are authorized to read. Nothing here is inferred by CAREVERSE: every
clinical-looking field is either entered by the patient or copied from an
uploaded document.
"""

from datetime import datetime
from typing import Literal, Optional, TypedDict

Gender = Literal["male", "female", "other", "unspecified"]


class PatientProfileDocument(TypedDict, total=False):
    _id: object
    patient_id: str                    # -> users._id, unique (1:1)
    full_name: str
    date_of_birth: Optional[str]       # ISO date string, not a Date object
    gender: Gender
    phone: Optional[str]
    address: Optional[str]
    # A patient-facing, free-text description of their own history. Never
    # generated or rewritten by the AI.
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


def serialize_profile(profile: PatientProfileDocument) -> dict:
    return {
        "id": str(profile["_id"]),
        "patient_id": profile.get("patient_id"),
        "full_name": profile.get("full_name", ""),
        "date_of_birth": profile.get("date_of_birth"),
        "gender": profile.get("gender", "unspecified"),
        "phone": profile.get("phone"),
        "address": profile.get("address"),
        "notes": profile.get("notes"),
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
    }
