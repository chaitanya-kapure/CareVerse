"""Patient controller: profile reads and updates.

Thin by design. The two rules that matter -- "is this caller a patient" and
"is this their record" -- are decided in `assert_own_records`, so neither the
route nor this controller re-implements authorization.
"""

from app.database import get_db
from app.middlewares.auth_middleware import assert_own_records
from app.models.user import UserDocument
from app.schemas.profile import PatientProfileUpdate
from app.services.profile_service import ProfileService


class PatientController:
    @staticmethod
    async def get_profile(user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return ProfileService(db).get(patient_id)

    @staticmethod
    async def update_profile(payload: PatientProfileUpdate, user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return ProfileService(db).update(patient_id, payload)
