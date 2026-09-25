"""Data layer: collection accessors, document shapes, serializers, indexes."""

from app.models.access import PatientAccessDocument, serialize_access
from app.models.collections import (
    ALL_COLLECTIONS,
    MEDICAL_DOCUMENTS,
    PATIENT_ACCESS,
    PATIENT_PROFILES,
    PATIENT_SUMMARIES,
    USERS,
    get_medical_documents,
    get_patient_access,
    get_patient_profiles,
    get_patient_summaries,
    get_users,
)
from app.models.indexes import ensure_indexes
from app.models.medical_document import (
    DocumentCategory,
    ExtractedData,
    ExtractionStatus,
    MedicalDocumentDocument,
    serialize_document,
)
from app.models.patient_profile import PatientProfileDocument, serialize_profile
from app.models.patient_summary import (
    PatientSummaryDocument,
    SummarySection,
    serialize_summary,
)
from app.models.user import UserDocument, UserRole, serialize_user

__all__ = [
    "ALL_COLLECTIONS",
    "DocumentCategory",
    "ExtractedData",
    "ExtractionStatus",
    "MEDICAL_DOCUMENTS",
    "MedicalDocumentDocument",
    "PATIENT_ACCESS",
    "PATIENT_PROFILES",
    "PATIENT_SUMMARIES",
    "PatientAccessDocument",
    "PatientProfileDocument",
    "PatientSummaryDocument",
    "SummarySection",
    "USERS",
    "UserDocument",
    "UserRole",
    "ensure_indexes",
    "get_medical_documents",
    "get_patient_access",
    "get_patient_profiles",
    "get_patient_summaries",
    "get_users",
    "serialize_access",
    "serialize_document",
    "serialize_profile",
    "serialize_summary",
    "serialize_user",
]
