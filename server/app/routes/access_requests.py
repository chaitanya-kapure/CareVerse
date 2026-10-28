"""Access request routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.controllers.access_request_controller import AccessRequestController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.access_request import (
    AccessRequestListResponse,
    AccessRequestResponse,
    ApproveAccessRequestRequest,
    CreateAccessRequestRequest,
    RejectAccessRequestRequest,
)

router = APIRouter(prefix="/access-requests", tags=["access-requests"])

DoctorUser = Annotated[UserDocument, Depends(require_roles("doctor"))]
PatientUser = Annotated[UserDocument, Depends(require_roles("patient"))]


@router.post(
    "",
    response_model=AccessRequestResponse,
    summary="Doctor initiates an access request for a patient by CareVerse ID",
)
async def create_access_request(
    payload: CreateAccessRequestRequest, user: DoctorUser
):
    return await AccessRequestController.create_request(payload, user)


@router.get(
    "/received",
    response_model=AccessRequestListResponse,
    summary="Patient lists incoming access requests",
)
async def list_received_requests(
    user: PatientUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await AccessRequestController.list_received(user, skip=skip, limit=limit)


@router.get(
    "/sent",
    response_model=AccessRequestListResponse,
    summary="Doctor lists outgoing access requests",
)
async def list_sent_requests(
    user: DoctorUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await AccessRequestController.list_sent(user, skip=skip, limit=limit)


@router.patch(
    "/{request_id}/approve",
    response_model=AccessRequestResponse,
    summary="Patient approves an access request",
)
async def approve_request(
    request_id: str,
    payload: ApproveAccessRequestRequest,
    user: PatientUser,
):
    return await AccessRequestController.approve(request_id, payload, user)


@router.patch(
    "/{request_id}/reject",
    response_model=AccessRequestResponse,
    summary="Patient rejects an access request",
)
async def reject_request(
    request_id: str,
    payload: RejectAccessRequestRequest,
    user: PatientUser,
):
    return await AccessRequestController.reject(request_id, payload, user)
