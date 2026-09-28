"""Patient profile endpoints.

Each route declares the path, the dependencies, and the response model.
All behaviour lives in PatientController.

`/me` rather than `/patients/{patientId}`: a patient editing their own
profile is not a resource lookup that could be pointed at someone else. There
is no id in the path to change, so there is no id to change *to*.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.patient_controller import PatientController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.profile import PatientProfileResponse, PatientProfileUpdate

router = APIRouter(prefix="/patients", tags=["patients"])

# The role gate. The server-side ownership check still happens per-request
# inside the controller via `assert_own_records`; this only decides which
# kinds of account may reach these handlers at all.
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
