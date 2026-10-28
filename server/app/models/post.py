"""posts collection."""
from datetime import datetime
from typing import Literal, Optional, TypedDict

PostType = Literal["text", "article", "question", "awareness"]


class PostDocument(TypedDict, total=False):
    _id: object
    author_id: str           # -> users._id
    author_role: str         # "patient" | "doctor"
    author_name: str         # denormalized for feed performance
    content: str
    post_type: PostType
    hashtags: list           # list[str]
    image_url: Optional[str]
    like_count: int
    comment_count: int
    save_count: int
    liked_by: list           # list[str] user_ids
    saved_by: list           # list[str] user_ids
    report_count: int
    is_hidden: bool
    created_at: datetime
    updated_at: datetime


def serialize_post(post: PostDocument, viewer_id: str = "") -> dict:
    liked_by = post.get("liked_by") or []
    saved_by = post.get("saved_by") or []
    return {
        "id": str(post["_id"]),
        "author_id": post.get("author_id"),
        "author_role": post.get("author_role"),
        "author_name": post.get("author_name", ""),
        "content": post.get("content", ""),
        "post_type": post.get("post_type", "text"),
        "hashtags": post.get("hashtags") or [],
        "image_url": post.get("image_url"),
        "like_count": post.get("like_count", 0),
        "comment_count": post.get("comment_count", 0),
        "save_count": post.get("save_count", 0),
        "viewer_has_liked": viewer_id in liked_by if viewer_id else False,
        "viewer_has_saved": viewer_id in saved_by if viewer_id else False,
        "created_at": post.get("created_at"),
        "updated_at": post.get("updated_at"),
    }
