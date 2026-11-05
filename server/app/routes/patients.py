"""Patient profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.patient_controller import PatientController
from app.controllers.summary_controller import SummaryController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.profile import (
    CareVerseIdResponse,
    PatientProfileResponse,
    PatientProfileUpdate,
)
from app.schemas.summary import PatientSummaryResponse

router = APIRouter(prefix="/patients", tags=["patients"])

# The role gate. The server-side ownership check still happens per-request
PatientUser = Annotated[UserDocument, Depends(require_roles("patient"))]


@router.get("/me", response_model=PatientProfileResponse, summary="Own profile")
async def get_profile(user: PatientUser):
    return await PatientController.get_profile(user)


@router.patch(
    "/me",
    response_model=PatientProfileResponse,
    summary="Edit basic details",
)
async def update_profile(payload: PatientProfileUpdate, user: PatientUser):
    """Partial update: only the fields present in the body are written."""
    return await PatientController.update_profile(payload, user)


@router.get(
    "/me/careverse-id",
    response_model=CareVerseIdResponse,
    summary="Get own 4-digit CareVerse ID",
)
async def get_my_careverse_id(user: PatientUser):
    """Return the patient's unique persistent CareVerse ID."""
    return await PatientController.get_careverse_id(user)


@router.get(
    "/me/summary",
    response_model=PatientSummaryResponse,
    summary="Summary assembled from the records you uploaded",
)
async def get_own_summary(user: PatientUser):
    """The caller's own summary, and only the caller's."""
    return await SummaryController.get_own(user)
