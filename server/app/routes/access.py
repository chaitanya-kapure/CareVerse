"""Patient's own access-management endpoints.

Mounted under the same `/patients/me` prefix as the profile and document
routes, and for the same reason: there is no patient id in the path, so there
is nothing for a caller to substitute. `assert_own_records` derives the
patient from the session inside the controller.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.controllers.access_controller import AccessController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.access import (
    AccessGrantListResponse,
    AccessGrantRequest,
    AccessGrantResponse,
)

router = APIRouter(prefix="/patients/me/access", tags=["access"])

PatientUser = Annotated[UserDocument, Depends(require_roles("patient"))]


@router.get(
    "",
    response_model=AccessGrantListResponse,
    summary="Doctors this patient has authorized",
)
async def list_grants(user: PatientUser):
    """Includes revoked grants, so a patient can see who *used to* have access."""
    return await AccessController.list_grants(user)


@router.post(
    "",
    response_model=AccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Authorize one doctor",
)
async def grant_access(payload: AccessGrantRequest, user: PatientUser):
    return await AccessController.grant(payload, user)


@router.delete(
    "/{access_id}",
    response_model=AccessGrantResponse,
    summary="Revoke a doctor's access",
)
async def revoke_access(access_id: str, user: PatientUser):
    return await AccessController.revoke(access_id, user)
