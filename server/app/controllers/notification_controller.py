"""Notification controller."""
from app.database import get_db
from app.models.user import UserDocument
from app.services.notification_service import NotificationService


class NotificationController:
    @staticmethod
    async def list_notifications(
        user: UserDocument, skip: int = 0, limit: int = 30
    ) -> dict:
        db = get_db()
        return NotificationService(db).list_for_user(
            user_id=str(user["_id"]), skip=skip, limit=limit
        )

    @staticmethod
    async def unread_count(user: UserDocument) -> dict:
        db = get_db()
        count = NotificationService(db).unread_count(user_id=str(user["_id"]))
        return {"unread_count": count}

    @staticmethod
    async def mark_read(notif_id: str, user: UserDocument) -> dict:
        db = get_db()
        NotificationService(db).mark_read(notif_id=notif_id, user_id=str(user["_id"]))
        return {"marked": True, "id": notif_id}

    @staticmethod
    async def mark_all_read(user: UserDocument) -> dict:
        db = get_db()
        NotificationService(db).mark_all_read(user_id=str(user["_id"]))
        return {"marked": True}
