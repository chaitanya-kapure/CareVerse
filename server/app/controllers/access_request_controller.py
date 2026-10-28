"""Access request controller."""
from app.database import get_db
from app.middlewares.auth_middleware import assert_own_records
from app.models.user import UserDocument
from app.schemas.access_request import (
    ApproveAccessRequestRequest,
    CreateAccessRequestRequest,
    RejectAccessRequestRequest,
)
from app.services.access_request_service import AccessRequestService


class AccessRequestController:
    @staticmethod
    async def create_request(
        payload: CreateAccessRequestRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        doctor_id = str(user["_id"])
        doctor_name = user.get("name", "Doctor")
        return AccessRequestService(db).create_request(
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            careverse_id=payload.careverse_id,
            purpose=payload.purpose,
            categories=payload.categories,
            duration_days=payload.duration_days,
        )

    @staticmethod
    async def list_received(
        user: UserDocument, skip: int = 0, limit: int = 20
    ) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return AccessRequestService(db).list_received(patient_id, skip=skip, limit=limit)

    @staticmethod
    async def list_sent(
        user: UserDocument, skip: int = 0, limit: int = 20
    ) -> dict:
        db = get_db()
        doctor_id = str(user["_id"])
        return AccessRequestService(db).list_sent(doctor_id, skip=skip, limit=limit)

    @staticmethod
    async def approve(
        request_id: str, payload: ApproveAccessRequestRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return AccessRequestService(db).approve(request_id, patient_id)

    @staticmethod
    async def reject(
        request_id: str, payload: RejectAccessRequestRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return AccessRequestService(db).reject(request_id, patient_id, payload.reason)
