"""Social controller."""
from typing import Optional

from app.database import get_db
from app.models.user import UserDocument
from app.schemas.social import (
    CreateCommentRequest,
    CreatePostRequest,
    ReportPostRequest,
)
from app.services.follow_service import FollowService
from app.services.social_service import SocialService


class SocialController:
    @staticmethod
    async def create_post(payload: CreatePostRequest, user: UserDocument) -> dict:
        db = get_db()
        return SocialService(db).create_post(
            author_id=str(user["_id"]),
            author_role=user.get("role", "patient"),
            author_name=user.get("name", "Anonymous"),
            content=payload.content,
            post_type=payload.post_type,
            hashtags=payload.hashtags,
            image_url=payload.image_url,
        )

    @staticmethod
    async def list_posts(
        viewer_id: str,
        skip: int = 0,
        limit: int = 20,
        hashtag: Optional[str] = None,
        author_id: Optional[str] = None,
        post_type: Optional[str] = None,
    ) -> dict:
        db = get_db()
        return SocialService(db).list_posts(
            viewer_id=viewer_id,
            skip=skip,
            limit=limit,
            hashtag=hashtag,
            author_id=author_id,
            post_type=post_type,
        )

    @staticmethod
    async def get_post(post_id: str, viewer_id: str = "") -> dict:
        db = get_db()
        return SocialService(db).get_post(post_id, viewer_id=viewer_id)

    @staticmethod
    async def delete_post(post_id: str, user: UserDocument) -> dict:
        db = get_db()
        return SocialService(db).delete_post(post_id, author_id=str(user["_id"]))

    @staticmethod
    async def toggle_like(post_id: str, user: UserDocument) -> dict:
        db = get_db()
        return SocialService(db).toggle_like(post_id, user_id=str(user["_id"]))

    @staticmethod
    async def toggle_save(post_id: str, user: UserDocument) -> dict:
        db = get_db()
        return SocialService(db).toggle_save(post_id, user_id=str(user["_id"]))

    @staticmethod
    async def report_post(
        post_id: str, payload: ReportPostRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        return SocialService(db).report_post(
            post_id, user_id=str(user["_id"]), reason=payload.reason
        )

    @staticmethod
    async def create_comment(
        post_id: str, payload: CreateCommentRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        return SocialService(db).create_comment(
            post_id=post_id,
            author_id=str(user["_id"]),
            author_name=user.get("name", "Anonymous"),
            content=payload.content,
        )

    @staticmethod
    async def list_comments(post_id: str, skip: int = 0, limit: int = 50) -> dict:
        db = get_db()
        return SocialService(db).list_comments(post_id, skip=skip, limit=limit)

    @staticmethod
    async def delete_comment(comment_id: str, user: UserDocument) -> dict:
        db = get_db()
        return SocialService(db).delete_comment(comment_id, author_id=str(user["_id"]))

    @staticmethod
    async def follow_user(target_user_id: str, user: UserDocument) -> dict:
        db = get_db()
        return FollowService(db).follow(follower_id=str(user["_id"]), followee_id=target_user_id)

    @staticmethod
    async def unfollow_user(target_user_id: str, user: UserDocument) -> dict:
        db = get_db()
        return FollowService(db).unfollow(follower_id=str(user["_id"]), followee_id=target_user_id)

    @staticmethod
    async def list_following(user: UserDocument, skip: int = 0, limit: int = 50) -> dict:
        db = get_db()
        return FollowService(db).list_following(follower_id=str(user["_id"]), skip=skip, limit=limit)
