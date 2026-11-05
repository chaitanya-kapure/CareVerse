"""Schemas for the doctor-access and grant endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.documents import (
    DocumentListResponse,
    MedicalDocumentDetailResponse,
)
from app.schemas.profile import PatientProfileResponse

# The reason a patient gives when sharing. Their words, kept short, never
# interpreted or rewritten.
MAX_NOTE_LENGTH = 500


# ======================================================================
# patient -> doctor (grants)
# ======================================================================


class AccessGrantRequest(BaseModel):
    """Body for granting one doctor access."""

    model_config = ConfigDict(str_strip_whitespace=True)

    doctor_id: str = Field(min_length=1, max_length=64)
    note: Optional[str] = Field(default=None, max_length=MAX_NOTE_LENGTH)

    @field_validator("doctor_id")
    @classmethod
    def _validate_doctor_id(cls, value: str) -> str:
        # Shape only. Whether the id names a real doctor is a service-level
        if len(value) != 24 or any(c not in "0123456789abcdefABCDEF" for c in value):
            raise ValueError("Doctor id is not valid")
        return value


class AccessGrantResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    doctor_name: str
    status: str
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    note: Optional[str] = None


class AccessGrantListResponse(BaseModel):
    items: list[AccessGrantResponse]
    total: int


# ======================================================================
# doctor -> patient (reads)
# ======================================================================


class DoctorPatientSummary(BaseModel):
    """One row in the doctor's authorized-patient list."""

    patient_id: str
    full_name: str
    date_of_birth: Optional[str] = None
    gender: str = "unspecified"
    document_count: int = 0
    has_profile: bool = True


class DoctorPatientListResponse(BaseModel):
    items: list[DoctorPatientSummary]
    total: int


# A doctor's view of a patient is the patient's own profile response. The
DoctorPatientProfileResponse = PatientProfileResponse

# Documents come back in the Phase 2 shapes, unchanged.
DoctorDocumentListResponse = DocumentListResponse
DoctorDocumentDetailResponse = MedicalDocumentDetailResponse
