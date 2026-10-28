"""comments collection."""
from datetime import datetime
from typing import TypedDict


class CommentDocument(TypedDict, total=False):
    _id: object
    post_id: str
    author_id: str
    author_name: str
    content: str
    created_at: datetime


def serialize_comment(comment: CommentDocument) -> dict:
    return {
        "id": str(comment["_id"]),
        "post_id": comment.get("post_id"),
        "author_id": comment.get("author_id"),
        "author_name": comment.get("author_name", ""),
        "content": comment.get("content", ""),
        "created_at": comment.get("created_at"),
    }
