"""notifications collection."""
from datetime import datetime
from typing import Literal, Optional, TypedDict

NotificationType = Literal[
    "access_request_received",
    "access_approved",
    "access_rejected",
    "access_revoked",
    "new_message",
    "new_follower",
    "post_liked",
    "post_commented",
    "connection_request",
]


class NotificationDocument(TypedDict, total=False):
    _id: object
    user_id: str
    type: NotificationType
    title: str
    body: str
    payload: dict               # arbitrary JSON context
    is_read: bool
    created_at: datetime


def serialize_notification(notif: NotificationDocument) -> dict:
    return {
        "id": str(notif["_id"]),
        "user_id": notif.get("user_id"),
        "type": notif.get("type"),
        "title": notif.get("title", ""),
        "body": notif.get("body", ""),
        "payload": notif.get("payload") or {},
        "is_read": notif.get("is_read", False),
        "created_at": notif.get("created_at"),
    }
