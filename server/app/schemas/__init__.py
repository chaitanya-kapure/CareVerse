"""Pydantic schemas: the API's validation and serialization layer."""

from app.schemas.access import (
    AccessGrantListResponse,
    AccessGrantRequest,
    AccessGrantResponse,
    DoctorDocumentDetailResponse,
    DoctorDocumentListResponse,
    DoctorPatientListResponse,
    DoctorPatientProfileResponse,
    DoctorPatientSummary,
)
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserRoleLiteral,
)
from app.schemas.common import ApiError, HealthResponse, Page, PageMeta
from app.schemas.documents import (
    DOCUMENT_CATEGORIES,
    DocumentListResponse,
    MedicalDocumentDetailResponse,
    MedicalDocumentSummaryResponse,
    UploadMeta,
)
from app.schemas.profile import (
    GENDERS,
    PatientProfileResponse,
    PatientProfileUpdate,
)

__all__ = [
    "AccessGrantListResponse",
    "AccessGrantRequest",
    "AccessGrantResponse",
    "ApiError",
    "DOCUMENT_CATEGORIES",
    "DocumentListResponse",
    "DoctorDocumentDetailResponse",
    "DoctorDocumentListResponse",
    "DoctorPatientListResponse",
    "DoctorPatientProfileResponse",
    "DoctorPatientSummary",
    "GENDERS",
    "HealthResponse",
    "LoginRequest",
    "MedicalDocumentDetailResponse",
    "MedicalDocumentSummaryResponse",
    "MessageResponse",
    "Page",
    "PageMeta",
    "PatientProfileResponse",
    "PatientProfileUpdate",
    "RegisterRequest",
    "TokenResponse",
    "UploadMeta",
    "UserResponse",
    "UserRoleLiteral",
]
