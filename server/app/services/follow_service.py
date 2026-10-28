"""Follow service — user follow/unfollow relationships."""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database

from app.models.collections import (
    get_doctor_profiles,
    get_follows,
    get_users,
)
from app.services.notification_service import NotificationService
from app.utils import errors

logger = logging.getLogger(__name__)


class FollowService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._follows = get_follows(db)
        self._doctor_profiles = get_doctor_profiles(db)
        self._users = get_users(db)
        self._notifs = NotificationService(db)

    def follow(self, follower_id: str, followee_id: str) -> dict:
        """Follow another user."""
        if follower_id == followee_id:
            raise errors.bad_request(
                "You cannot follow yourself",
                code="SELF_FOLLOW_NOT_ALLOWED",
            )

        if not ObjectId.is_valid(followee_id):
            raise errors.not_found("Target user not found", code="USER_NOT_FOUND")

        target_user = self._users.find_one({"_id": ObjectId(followee_id)})
        if not target_user:
            raise errors.not_found("Target user not found", code="USER_NOT_FOUND")

        now = datetime.now(timezone.utc)
        res = self._follows.update_one(
            {"follower_id": follower_id, "followee_id": followee_id},
            {
                "$setOnInsert": {
                    "follower_id": follower_id,
                    "followee_id": followee_id,
                    "created_at": now,
                }
            },
            upsert=True,
        )

        if res.upserted_id is not None:
            if target_user.get("role") == "doctor":
                self._doctor_profiles.update_one(
                    {"user_id": followee_id},
                    {"$inc": {"follower_count": 1}},
                )

            follower = self._users.find_one({"_id": ObjectId(follower_id)}) if ObjectId.is_valid(follower_id) else None
            follower_name = follower.get("name", "Someone") if follower else "Someone"

            self._notifs.send(
                user_id=followee_id,
                notif_type="new_follower",
                title="New Follower",
                body=f"{follower_name} started following you.",
                payload={"follower_id": follower_id},
            )

        return {"following": True, "followee_id": followee_id}

    def unfollow(self, follower_id: str, followee_id: str) -> dict:
        """Unfollow a user."""
        res = self._follows.delete_one(
            {"follower_id": follower_id, "followee_id": followee_id}
        )
        if res.deleted_count > 0:
            self._doctor_profiles.update_one(
                {"user_id": followee_id, "follower_count": {"$gt": 0}},
                {"$inc": {"follower_count": -1}},
            )
        return {"following": False, "followee_id": followee_id}

    def is_following(self, follower_id: str, followee_id: str) -> bool:
        """Check if follower follows followee."""
        return (
            self._follows.count_documents(
                {"follower_id": follower_id, "followee_id": followee_id}
            )
            > 0
        )

    def list_following(
        self, follower_id: str, skip: int = 0, limit: int = 50
    ) -> dict:
        """List user IDs followed by the user."""
        filter_q = {"follower_id": follower_id}
        total = self._follows.count_documents(filter_q)
        cursor = (
            self._follows.find(filter_q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [f["followee_id"] for f in cursor]
        return {"items": items, "total": total}

    def list_followers(
        self, followee_id: str, skip: int = 0, limit: int = 50
    ) -> dict:
        """List user IDs following the target user."""
        filter_q = {"followee_id": followee_id}
        total = self._follows.count_documents(filter_q)
        cursor = (
            self._follows.find(filter_q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [f["follower_id"] for f in cursor]
        return {"items": items, "total": total}
