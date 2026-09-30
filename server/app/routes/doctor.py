"""Doctor endpoints.

Read-only. A doctor sees the records of patients who authorized them and can
do nothing else to them: no upload, no edit, no delete. The patient remains
the owner of their records, and there is deliberately no doctor-side route
that could change one.

Note the shape of the URLs: `{patient_id}` is in the path, which is exactly
why `assert_patient_access` is called on every single handler. An id in a path
is attacker-controlled input, and the only thing standing between a doctor and
another patient's medical history is that check.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.doctor_controller import DoctorController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.access import (
    DoctorDocumentDetailResponse,
    DoctorDocumentListResponse,
    DoctorPatientListResponse,
    DoctorPatientProfileResponse,
)

router = APIRouter(prefix="/doctor", tags=["doctor"])

# Role gate. It answers "is this account a doctor at all"; it says nothing
# about which patients that doctor may read, which is the separate
# per-request check every handler below performs.
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
