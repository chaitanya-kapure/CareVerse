"""Doctor profile routes."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.controllers.doctor_profile_controller import DoctorProfileController
from app.middlewares.auth_middleware import CurrentUser, require_roles
from app.models.user import UserDocument
from app.schemas.doctor_profile import (
    DoctorDiscoveryResponse,
    DoctorProfileResponse,
    DoctorProfileUpdate,
)

router = APIRouter(prefix="/doctor-profiles", tags=["doctor-profiles"])

DoctorUser = Annotated[UserDocument, Depends(require_roles("doctor"))]


@router.get(
    "/me",
    response_model=DoctorProfileResponse,
    summary="Get authenticated doctor's profile",
)
async def get_my_profile(user: DoctorUser):
    return await DoctorProfileController.get_own_profile(user)


@router.patch(
    "/me",
    response_model=DoctorProfileResponse,
    summary="Update authenticated doctor's profile",
)
async def update_my_profile(payload: DoctorProfileUpdate, user: DoctorUser):
    return await DoctorProfileController.update_own_profile(payload, user)


@router.get(
    "/",
    response_model=DoctorDiscoveryResponse,
    summary="Search and discover doctors",
)
async def search_doctors(
    user: CurrentUser,
    specialty: Optional[str] = Query(None, description="Filter by doctor specialty"),
    name: Optional[str] = Query(None, description="Filter by doctor name"),
    verified_only: bool = Query(False, description="Filter verified doctors only"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await DoctorProfileController.search_doctors(
        specialty=specialty,
        name=name,
        verified_only=verified_only,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{user_id}",
    response_model=DoctorProfileResponse,
    summary="Get public profile of a doctor",
)
async def get_doctor_profile(user_id: str, user: CurrentUser):
    return await DoctorProfileController.get_public_profile(user_id)
