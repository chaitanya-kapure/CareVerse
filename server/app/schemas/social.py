"""Schemas for social posts, comments, likes, saves, and reports."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CreatePostRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=5000)
    post_type: Literal["text", "article", "question", "awareness"] = "text"
    hashtags: Optional[list[str]] = Field(default_factory=list)
    image_url: Optional[str] = None


class PostResponse(BaseModel):
    id: str
    author_id: Optional[str] = None
    author_role: Optional[str] = None
    author_name: str = ""
    content: str
    post_type: str = "text"
    hashtags: list[str] = []
    image_url: Optional[str] = None
    like_count: int = 0
    comment_count: int = 0
    save_count: int = 0
    viewer_has_liked: bool = False
    viewer_has_saved: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PostListResponse(BaseModel):
    items: list[PostResponse]
    total: int


class ToggleLikeResponse(BaseModel):
    post_id: str
    like_count: int
    viewer_has_liked: bool


class ToggleSaveResponse(BaseModel):
    post_id: str
    save_count: int
    viewer_has_saved: bool


class ReportPostRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: Optional[str] = Field(default=None, max_length=500)


class ReportPostResponse(BaseModel):
    reported: bool
    post_id: str


class CreateCommentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_id: str
    author_name: str
    content: str
    created_at: Optional[datetime] = None


class CommentListResponse(BaseModel):
    items: list[CommentResponse]
    total: int
