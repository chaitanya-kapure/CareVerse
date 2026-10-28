"""Discovery controller — patient discovery for doctors."""
from bson import ObjectId

from app.database import get_db
from app.models.collections import get_patient_profiles, get_users
from app.models.user import UserDocument
from app.services.careverse_id_service import CareVerseIdService
from app.utils import errors


class DiscoveryController:
    @staticmethod
    async def lookup_patient_by_careverse_id(careverse_id: str, user: UserDocument) -> dict:
        """Look up patient minimal public info by CareVerse ID (doctors only).
        
        Never returns clinical data, document counts, medical history, or profile notes.
        """
        clean_id = (careverse_id or "").strip()
        if len(clean_id) != 4 or not clean_id.isdigit():
            raise errors.bad_request(
                "CareVerse ID must be exactly 4 digits", code="INVALID_CAREVERSE_ID"
            )

        db = get_db()
        id_service = CareVerseIdService(db)
        patient_id = id_service.lookup_patient_id(clean_id)
        if not patient_id:
            raise errors.not_found(
                "Patient with this CareVerse ID was not found",
                code="PATIENT_NOT_FOUND",
            )

        user_doc = get_users(db).find_one({"_id": ObjectId(patient_id)}) if ObjectId.is_valid(patient_id) else None
        if not user_doc or user_doc.get("role") != "patient":
            raise errors.not_found(
                "Patient with this CareVerse ID was not found",
                code="PATIENT_NOT_FOUND",
            )

        profile_doc = get_patient_profiles(db).find_one({"patient_id": patient_id})
        full_name = (profile_doc.get("full_name") if profile_doc else "") or user_doc.get("name", "Patient")
        gender = profile_doc.get("gender", "unspecified") if profile_doc else "unspecified"

        return {
            "patient_id": patient_id,
            "careverse_id": clean_id,
            "full_name": full_name,
            "gender": gender,
        }
