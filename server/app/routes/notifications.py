"""Notification routes."""
from fastapi import APIRouter, Query

from app.controllers.notification_controller import NotificationController
from app.middlewares.auth_middleware import CurrentUser
from app.schemas.notifications import (
    NotificationListResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications for current user",
)
async def list_notifications(
    user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
):
    return await NotificationController.list_notifications(user, skip=skip, limit=limit)


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get count of unread notifications",
)
async def get_unread_count(user: CurrentUser):
    return await NotificationController.unread_count(user)


@router.patch(
    "/read-all",
    summary="Mark all notifications as read",
)
async def mark_all_read(user: CurrentUser):
    return await NotificationController.mark_all_read(user)


@router.patch(
    "/{notif_id}/read",
    summary="Mark a notification as read",
)
async def mark_notification_read(notif_id: str, user: CurrentUser):
    return await NotificationController.mark_read(notif_id, user)
