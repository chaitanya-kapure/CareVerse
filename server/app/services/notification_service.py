"""Notification delivery — in-app only."""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database

from app.models.collections import get_notifications
from app.models.notification import NotificationType, serialize_notification

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: Database) -> None:
        self._notifs = get_notifications(db)

    def send(
        self,
        user_id: str,
        notif_type: NotificationType,
        title: str,
        body: str,
        payload: Optional[dict] = None,
    ) -> None:
        self._notifs.insert_one(
            {
                "user_id": user_id,
                "type": notif_type,
                "title": title,
                "body": body,
                "payload": payload or {},
                "is_read": False,
                "created_at": datetime.now(timezone.utc),
            }
        )

    def list_for_user(self, user_id: str, skip: int = 0, limit: int = 30) -> dict:
        cursor = (
            self._notifs.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [serialize_notification(n) for n in cursor]
        total = self._notifs.count_documents({"user_id": user_id})
        return {"items": items, "total": total}

    def unread_count(self, user_id: str) -> int:
        return self._notifs.count_documents({"user_id": user_id, "is_read": False})

    def mark_read(self, notif_id: str, user_id: str) -> None:
        if not ObjectId.is_valid(notif_id):
            return
        self._notifs.update_one(
            {"_id": ObjectId(notif_id), "user_id": user_id},
            {"$set": {"is_read": True}},
        )

    def mark_all_read(self, user_id: str) -> None:
        self._notifs.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True}},
        )
