"""Doctor endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.doctor_controller import DoctorController
from app.controllers.summary_controller import SummaryController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.access import (
    DoctorDocumentDetailResponse,
    DoctorDocumentListResponse,
    DoctorPatientListResponse,
    DoctorPatientProfileResponse,
)
from app.schemas.summary import PatientSummaryResponse

router = APIRouter(prefix="/doctor", tags=["doctor"])

# Role gate. It answers "is this account a doctor at all"; it says nothing
DoctorUser = Annotated[UserDocument, Depends(require_roles("doctor"))]


@router.get(
    "/patients",
    response_model=DoctorPatientListResponse,
    summary="Patients who have authorized this doctor",
)
async def list_patients(user: DoctorUser):
    return await DoctorController.list_patients(user)


@router.get(
    "/patients/{patient_id}",
    response_model=DoctorPatientProfileResponse,
    summary="One authorized patient's profile",
)
async def get_patient(patient_id: str, user: DoctorUser):
    return await DoctorController.get_patient(patient_id, user)


@router.get(
    "/patients/{patient_id}/documents",
    response_model=DoctorDocumentListResponse,
    summary="An authorized patient's record list",
)
async def list_patient_documents(patient_id: str, user: DoctorUser):
    return await DoctorController.list_documents(patient_id, user)


@router.get(
    "/patients/{patient_id}/documents/{document_id}",
    response_model=DoctorDocumentDetailResponse,
    summary="One record, including its extracted text",
)
async def get_patient_document(
    patient_id: str, document_id: str, user: DoctorUser
):
    return await DoctorController.get_document(patient_id, document_id, user)


@router.get(
    "/patients/{patient_id}/documents/{document_id}/file",
    summary="Stream an authorized patient's original PDF",
)
async def get_patient_document_file(
    patient_id: str, document_id: str, user: DoctorUser
):
    return await DoctorController.get_document_file(patient_id, document_id, user)


@router.get(
    "/patients/{patient_id}/summary",
    response_model=PatientSummaryResponse,
    summary="The patient's summary, generated on demand",
)
async def get_patient_summary(patient_id: str, user: DoctorUser):
    """Read-only, like every other route on this router."""
    return await SummaryController.get_for_doctor(patient_id, user)


@router.post(
    "/patients/{patient_id}/summary/regenerate",
    response_model=PatientSummaryResponse,
    summary="Force the summary to be rebuilt from the current records",
)
async def regenerate_patient_summary(patient_id: str, user: DoctorUser):
    """Rebuild now, ignoring the staleness check."""
    return await SummaryController.regenerate_for_doctor(patient_id, user)
