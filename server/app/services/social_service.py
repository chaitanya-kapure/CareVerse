"""Social service — posts, comments, likes, saves, and reports."""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo.database import Database

from app.models.collections import (
    get_comments,
    get_doctor_profiles,
    get_posts,
    get_users,
)
from app.models.comment import CommentDocument, serialize_comment
from app.models.post import PostDocument, PostType, serialize_post
from app.services.notification_service import NotificationService
from app.utils import errors

logger = logging.getLogger(__name__)


def extract_hashtags(content: str, explicit_tags: Optional[list[str]] = None) -> list[str]:
    tags = set()
    if explicit_tags:
        for t in explicit_tags:
            cleaned = t.strip().lstrip("#").lower()
            if cleaned:
                tags.add(cleaned)
    for match in re.finditer(r"#(\w+)", content):
        tags.add(match.group(1).lower())
    return sorted(list(tags))


class SocialService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._posts = get_posts(db)
        self._comments = get_comments(db)
        self._doctor_profiles = get_doctor_profiles(db)
        self._users = get_users(db)
        self._notifs = NotificationService(db)

    def create_post(
        self,
        author_id: str,
        author_role: str,
        author_name: str,
        content: str,
        post_type: PostType = "text",
        hashtags: Optional[list[str]] = None,
        image_url: Optional[str] = None,
    ) -> dict:
        """Create a new post."""
        now = datetime.now(timezone.utc)
        all_hashtags = extract_hashtags(content, hashtags)

        doc: PostDocument = {
            "author_id": author_id,
            "author_role": author_role,
            "author_name": author_name or "Anonymous",
            "content": content.strip(),
            "post_type": post_type,
            "hashtags": all_hashtags,
            "image_url": image_url,
            "like_count": 0,
            "comment_count": 0,
            "save_count": 0,
            "liked_by": [],
            "saved_by": [],
            "report_count": 0,
            "is_hidden": False,
            "created_at": now,
            "updated_at": now,
        }

        res = self._posts.insert_one(doc)
        doc["_id"] = res.inserted_id

        # If author is doctor, update post_count
        if author_role == "doctor":
            self._doctor_profiles.update_one(
                {"user_id": author_id},
                {"$inc": {"post_count": 1}},
            )

        return serialize_post(doc, viewer_id=author_id)

    def list_posts(
        self,
        viewer_id: str = "",
        skip: int = 0,
        limit: int = 20,
        hashtag: Optional[str] = None,
        author_id: Optional[str] = None,
        post_type: Optional[str] = None,
    ) -> dict:
        """List visible posts, ordered newest first."""
        filter_q: dict[str, Any] = {"is_hidden": {"$ne": True}}

        if hashtag:
            filter_q["hashtags"] = hashtag.strip().lstrip("#").lower()
        if author_id:
            filter_q["author_id"] = author_id
        if post_type:
            filter_q["post_type"] = post_type

        total = self._posts.count_documents(filter_q)
        cursor = (
            self._posts.find(filter_q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [serialize_post(p, viewer_id=viewer_id) for p in cursor]
        return {"items": items, "total": total}

    def get_post(self, post_id: str, viewer_id: str = "") -> dict:
        """Get a single post."""
        if not ObjectId.is_valid(post_id):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        post = self._posts.find_one({"_id": ObjectId(post_id)})
        if not post or post.get("is_hidden"):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        return serialize_post(post, viewer_id=viewer_id)

    def delete_post(self, post_id: str, author_id: str) -> dict:
        """Delete a post (author only)."""
        if not ObjectId.is_valid(post_id):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        post = self._posts.find_one({"_id": ObjectId(post_id)})
        if not post:
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        if post.get("author_id") != author_id:
            raise errors.forbidden(
                "You cannot delete another user's post",
                code="FORBIDDEN_POST_DELETE",
            )

        self._posts.delete_one({"_id": ObjectId(post_id)})
        self._comments.delete_many({"post_id": post_id})

        if post.get("author_role") == "doctor":
            self._doctor_profiles.update_one(
                {"user_id": author_id, "post_count": {"$gt": 0}},
                {"$inc": {"post_count": -1}},
            )

        return {"deleted": True, "id": post_id}

    def toggle_like(self, post_id: str, user_id: str) -> dict:
        """Like or unlike a post."""
        if not ObjectId.is_valid(post_id):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        post = self._posts.find_one({"_id": ObjectId(post_id)})
        if not post or post.get("is_hidden"):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        liked_by = post.get("liked_by") or []
        user_name = ""
        if user_id not in liked_by:
            self._posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$addToSet": {"liked_by": user_id}, "$inc": {"like_count": 1}},
            )
            has_liked = True
            # Notify author
            if post.get("author_id") != user_id:
                u = self._users.find_one({"_id": ObjectId(user_id)}) if ObjectId.is_valid(user_id) else None
                user_name = u.get("name", "Someone") if u else "Someone"
                self._notifs.send(
                    user_id=post["author_id"],
                    notif_type="post_liked",
                    title="Post Liked",
                    body=f"{user_name} liked your post.",
                    payload={"post_id": post_id, "user_id": user_id},
                )
        else:
            self._posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$pull": {"liked_by": user_id}, "$inc": {"like_count": -1}},
            )
            has_liked = False

        updated = self._posts.find_one({"_id": ObjectId(post_id)})
        return {
            "post_id": post_id,
            "like_count": updated.get("like_count", 0),
            "viewer_has_liked": has_liked,
        }

    def toggle_save(self, post_id: str, user_id: str) -> dict:
        """Bookmark or unbookmark a post."""
        if not ObjectId.is_valid(post_id):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        post = self._posts.find_one({"_id": ObjectId(post_id)})
        if not post or post.get("is_hidden"):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        saved_by = post.get("saved_by") or []
        if user_id not in saved_by:
            self._posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$addToSet": {"saved_by": user_id}, "$inc": {"save_count": 1}},
            )
            has_saved = True
        else:
            self._posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$pull": {"saved_by": user_id}, "$inc": {"save_count": -1}},
            )
            has_saved = False

        updated = self._posts.find_one({"_id": ObjectId(post_id)})
        return {
            "post_id": post_id,
            "save_count": updated.get("save_count", 0),
            "viewer_has_saved": has_saved,
        }

    def report_post(self, post_id: str, user_id: str, reason: Optional[str] = None) -> dict:
        """Report inappropriate post."""
        if not ObjectId.is_valid(post_id):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        post = self._posts.find_one({"_id": ObjectId(post_id)})
        if not post:
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        self._posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"report_count": 1}},
        )
        return {"reported": True, "post_id": post_id}

    def create_comment(
        self,
        post_id: str,
        author_id: str,
        author_name: str,
        content: str,
    ) -> dict:
        """Add a comment to a post."""
        if not ObjectId.is_valid(post_id):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        post = self._posts.find_one({"_id": ObjectId(post_id)})
        if not post or post.get("is_hidden"):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        now = datetime.now(timezone.utc)
        doc: CommentDocument = {
            "post_id": post_id,
            "author_id": author_id,
            "author_name": author_name or "Anonymous",
            "content": content.strip(),
            "created_at": now,
        }

        res = self._comments.insert_one(doc)
        doc["_id"] = res.inserted_id

        self._posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"comment_count": 1}},
        )

        if post.get("author_id") != author_id:
            self._notifs.send(
                user_id=post["author_id"],
                notif_type="post_commented",
                title="New Comment",
                body=f"{author_name} commented on your post.",
                payload={"post_id": post_id, "comment_id": str(doc["_id"])},
            )

        return serialize_comment(doc)

    def list_comments(self, post_id: str, skip: int = 0, limit: int = 50) -> dict:
        """List comments for a post, oldest first."""
        if not ObjectId.is_valid(post_id):
            raise errors.not_found("Post not found", code="POST_NOT_FOUND")

        filter_q = {"post_id": post_id}
        total = self._comments.count_documents(filter_q)
        cursor = (
            self._comments.find(filter_q)
            .sort("created_at", 1)
            .skip(skip)
            .limit(limit)
        )
        items = [serialize_comment(c) for c in cursor]
        return {"items": items, "total": total}

    def delete_comment(self, comment_id: str, author_id: str) -> dict:
        """Delete a comment (author only)."""
        if not ObjectId.is_valid(comment_id):
            raise errors.not_found("Comment not found", code="COMMENT_NOT_FOUND")

        comment = self._comments.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            raise errors.not_found("Comment not found", code="COMMENT_NOT_FOUND")

        if comment.get("author_id") != author_id:
            raise errors.forbidden(
                "You cannot delete another user's comment",
                code="FORBIDDEN_COMMENT_DELETE",
            )

        self._comments.delete_one({"_id": ObjectId(comment_id)})
        self._posts.update_one(
            {"_id": ObjectId(comment["post_id"]), "comment_count": {"$gt": 0}},
            {"$inc": {"comment_count": -1}},
        )

        return {"deleted": True, "id": comment_id}
