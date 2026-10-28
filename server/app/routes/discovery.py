"""Discovery routes — patient lookup by CareVerse ID for doctors."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.discovery_controller import DiscoveryController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.discovery import PatientDiscoveryResponse

router = APIRouter(prefix="/discovery", tags=["discovery"])

DoctorUser = Annotated[UserDocument, Depends(require_roles("doctor"))]


@router.get(
    "/patient/{careverse_id}",
    response_model=PatientDiscoveryResponse,
    summary="Look up a patient by 4-digit CareVerse ID (doctors only)",
)
async def lookup_patient(careverse_id: str, user: DoctorUser):
    return await DiscoveryController.lookup_patient_by_careverse_id(careverse_id, user)


@router.get(
    "/patients/{careverse_id}",
    response_model=PatientDiscoveryResponse,
    summary="Look up a patient by 4-digit CareVerse ID (doctors only, alias)",
)
async def lookup_patients_alias(careverse_id: str, user: DoctorUser):
    return await DiscoveryController.lookup_patient_by_careverse_id(careverse_id, user)
