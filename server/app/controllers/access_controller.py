"""Patient-side grant management.

The MVP mechanism for establishing doctor access: a patient authorizes one
specific doctor by id. There is no request, no invitation code, no approval
step and no doctor directory -- a patient who wants to share their records
already knows which doctor they are dealing with, and building a way to
*discover* doctors would be a feature with privacy costs and no purpose here.

The direction matters. These routes can only ever create a grant *for the
caller*, because `assert_own_records` derives the patient id from the session
rather than from the request. There is no body field, path segment or query
parameter through which a patient could name a different patient, so this
endpoint cannot be used to grant access to somebody else's records even by
mistake.
"""

from app.database import get_db
from app.middlewares.auth_middleware import assert_own_records
from app.models.user import UserDocument
from app.schemas.access import AccessGrantRequest
from app.services.access_service import AccessService


class AccessController:
    @staticmethod
    async def list_grants(user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        items = AccessService(db).list_for_patient(patient_id)
        return {"items": items, "total": len(items)}

    @staticmethod
    async def grant(payload: AccessGrantRequest, user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return AccessService(db).grant(patient_id, payload.doctor_id, payload.note)

    @staticmethod
    async def revoke(access_id: str, user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return AccessService(db).revoke(patient_id, access_id)
