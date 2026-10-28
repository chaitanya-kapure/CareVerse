"""Doctor profile service — profiles and discovery."""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.models.collections import get_doctor_profiles, get_users
from app.models.doctor_profile import (
    DoctorProfileDocument,
    serialize_doctor_profile,
)
from app.utils import errors

logger = logging.getLogger(__name__)


class DoctorProfileService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._profiles = get_doctor_profiles(db)
        self._users = get_users(db)

    def get_or_create(self, user_id: str, user_name: str = "") -> dict:
        """Return doctor profile or create a blank one."""
        now = datetime.now(timezone.utc)
        self._profiles.update_one(
            {"user_id": user_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "specialty": "",
                    "qualifications": "",
                    "experience_years": None,
                    "bio": "",
                    "location": None,
                    "verification_status": "unverified",
                    "profile_image_url": None,
                    "follower_count": 0,
                    "post_count": 0,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        doc = self._profiles.find_one({"user_id": user_id})
        if not user_name:
            user_name = self._resolve_user_name(user_id)
        return serialize_doctor_profile(doc, user_name)

    def update(self, user_id: str, data: dict[str, Any]) -> dict:
        """Update doctor's own profile fields."""
        allowed_fields = {
            "specialty",
            "qualifications",
            "experience_years",
            "bio",
            "location",
            "profile_image_url",
        }
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        update_data["updated_at"] = datetime.now(timezone.utc)

        doc = self._profiles.find_one_and_update(
            {"user_id": user_id},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            # If not yet created, create and update
            self.get_or_create(user_id)
            doc = self._profiles.find_one_and_update(
                {"user_id": user_id},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER,
            )

        user_name = self._resolve_user_name(user_id)
        return serialize_doctor_profile(doc, user_name)

    def get_by_user_id(self, user_id: str) -> dict:
        """Get public doctor profile by doctor user_id."""
        user = self._get_doctor_user(user_id)
        if not user:
            raise errors.not_found("Doctor not found", code="DOCTOR_NOT_FOUND")

        doc = self._profiles.find_one({"user_id": user_id})
        if not doc:
            return self.get_or_create(user_id, user.get("name", ""))

        return serialize_doctor_profile(doc, user.get("name", ""))

    def search(
        self,
        specialty: Optional[str] = None,
        name: Optional[str] = None,
        verified_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """Search and discover doctors with filtering and pagination."""
        filter_q: dict[str, Any] = {}
        if specialty and specialty.strip():
            filter_q["specialty"] = {"$regex": specialty.strip(), "$options": "i"}
        if verified_only:
            filter_q["verification_status"] = "verified"

        user_name_map: dict[str, str] = {}
        if name and name.strip():
            users_cursor = self._users.find(
                {
                    "role": "doctor",
                    "name": {"$regex": name.strip(), "$options": "i"},
                }
            )
            for u in users_cursor:
                user_name_map[str(u["_id"])] = u.get("name", "")
            filter_q["user_id"] = {"$in": list(user_name_map.keys())}

        total = self._profiles.count_documents(filter_q)
        cursor = (
            self._profiles.find(filter_q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = list(cursor)

        # Batch load any missing user names
        missing_ids = [
            doc["user_id"]
            for doc in docs
            if doc.get("user_id") and doc["user_id"] not in user_name_map
        ]
        if missing_ids:
            valid_obj_ids = [ObjectId(uid) for uid in missing_ids if ObjectId.is_valid(uid)]
            if valid_obj_ids:
                for u in self._users.find({"_id": {"$in": valid_obj_ids}}):
                    user_name_map[str(u["_id"])] = u.get("name", "")

        items = [
            serialize_doctor_profile(
                doc, user_name_map.get(doc.get("user_id", ""), "")
            )
            for doc in docs
        ]
        return {"items": items, "total": total}

    def _resolve_user_name(self, user_id: str) -> str:
        if not ObjectId.is_valid(user_id):
            return ""
        user = self._users.find_one({"_id": ObjectId(user_id)})
        return user.get("name", "") if user else ""

    def _get_doctor_user(self, user_id: str) -> Optional[dict]:
        if not ObjectId.is_valid(user_id):
            return None
        user = self._users.find_one({"_id": ObjectId(user_id)})
        if not user or user.get("role") != "doctor":
            return None
        return user
