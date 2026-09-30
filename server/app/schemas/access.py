"""Schemas for the doctor-access and grant endpoints.

Two directions, kept in one file because they are the two sides of the same
row in `patient_access`:

  * `AccessGrant*`        -- what a patient grants and what they can see.
  * `DoctorPatient*`      -- what an authorized doctor may read.

The doctor's view of a document reuses the Phase 2 response models exactly
rather than declaring a parallel set. A record a doctor sees and a record the
patient sees are the same object; a second schema for the doctor would be an
invitation for the two to drift apart, and the doctor's copy is the one with
fewer fields to check.
"""

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
    """Body for granting one doctor access.

    `doctor_id` is the only field, and it is the doctor being *authorized* --
    not a patient being targeted. The route carries no patient id, so the
    grant is always issued by the caller on their own behalf.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    doctor_id: str = Field(min_length=1, max_length=64)
    note: Optional[str] = Field(default=None, max_length=MAX_NOTE_LENGTH)

    @field_validator("doctor_id")
    @classmethod
    def _validate_doctor_id(cls, value: str) -> str:
        # Shape only. Whether the id names a real doctor is a service-level
        # question, answered with the same 404 a patient would get for any
        # other unknown id.
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
    """One row in the doctor's authorized-patient list.

    Name, the identifiers already on the profile, and how many records the
    patient has. No derived field, no health summary, no trend: a count of
    uploaded PDFs is a fact about the file store, not a statement about the
    patient.
    """

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
# patient is not a reduced or filtered version of themselves: the same
# serializer and the same fields, so a doctor and the patient read identical
# data and there is no second shape to audit.
DoctorPatientProfileResponse = PatientProfileResponse

# Documents come back in the Phase 2 shapes, unchanged.
DoctorDocumentListResponse = DocumentListResponse
DoctorDocumentDetailResponse = MedicalDocumentDetailResponse
