"""Doctor profile controller."""
from app.database import get_db
from app.models.user import UserDocument
from app.schemas.doctor_profile import DoctorProfileUpdate
from app.services.doctor_profile_service import DoctorProfileService


class DoctorProfileController:
    @staticmethod
    async def get_own_profile(user: UserDocument) -> dict:
        db = get_db()
        return DoctorProfileService(db).get_or_create(str(user["_id"]), user.get("name", ""))

    @staticmethod
    async def update_own_profile(payload: DoctorProfileUpdate, user: UserDocument) -> dict:
        db = get_db()
        return DoctorProfileService(db).update(
            str(user["_id"]), payload.model_dump(exclude_unset=True)
        )

    @staticmethod
    async def get_public_profile(user_id: str) -> dict:
        db = get_db()
        return DoctorProfileService(db).get_by_user_id(user_id)

    @staticmethod
    async def search_doctors(
        specialty: str | None = None,
        name: str | None = None,
        verified_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        db = get_db()
        return DoctorProfileService(db).search(
            specialty=specialty,
            name=name,
            verified_only=verified_only,
            skip=skip,
            limit=limit,
        )
