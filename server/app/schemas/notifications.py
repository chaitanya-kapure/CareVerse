"""Schemas for notifications."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    type: str
    title: str = ""
    body: str = ""
    payload: dict[str, Any] = {}
    is_read: bool = False
    created_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int


class UnreadCountResponse(BaseModel):
    unread_count: int
