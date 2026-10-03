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
from app.controllers.summary_controller import SummaryController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.profile import PatientProfileResponse, PatientProfileUpdate
from app.schemas.summary import PatientSummaryResponse

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


@router.get(
    "/me/summary",
    response_model=PatientSummaryResponse,
    summary="Summary assembled from the records you uploaded",
)
async def get_own_summary(user: PatientUser):
    """The caller's own summary, and only the caller's.

    `/me` for the same reason as every other route in this file: there is no
    patient id in the path, so there is no id to change to somebody else's.
    The response is the same document the doctor sees -- `SummaryService` does
    not know or care which of the two is asking -- so a patient and their
    clinician are always reading the same summary, not two similar ones.

    Returns a generated-on-demand summary rather than a 404. It is assembled
    entirely from records this patient already uploaded, and a patient who has
    uploaded nothing gets a real summary whose every section says so.
    """
    return await SummaryController.get_own(user)
