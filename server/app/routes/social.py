"""Social routes."""
from typing import Optional

from fastapi import APIRouter, Query

from app.controllers.social_controller import SocialController
from app.middlewares.auth_middleware import CurrentUser
from app.schemas.social import (
    CommentListResponse,
    CommentResponse,
    CreateCommentRequest,
    CreatePostRequest,
    PostListResponse,
    PostResponse,
    ReportPostRequest,
    ReportPostResponse,
    ToggleLikeResponse,
    ToggleSaveResponse,
)

router = APIRouter(prefix="/social", tags=["social"])


@router.post("/posts", response_model=PostResponse, summary="Create a new post")
async def create_post(payload: CreatePostRequest, user: CurrentUser):
    return await SocialController.create_post(payload, user)


@router.get("/posts", response_model=PostListResponse, summary="List social feed posts")
async def list_posts(
    user: CurrentUser,
    hashtag: Optional[str] = Query(None, description="Filter by hashtag"),
    author_id: Optional[str] = Query(None, description="Filter by author user ID"),
    post_type: Optional[str] = Query(None, description="Filter by post type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    viewer_id = str(user["_id"]) if user else ""
    return await SocialController.list_posts(
        viewer_id=viewer_id,
        skip=skip,
        limit=limit,
        hashtag=hashtag,
        author_id=author_id,
        post_type=post_type,
    )


@router.get("/posts/{post_id}", response_model=PostResponse, summary="Get a post by ID")
async def get_post(post_id: str, user: CurrentUser):
    viewer_id = str(user["_id"]) if user else ""
    return await SocialController.get_post(post_id, viewer_id=viewer_id)


@router.delete("/posts/{post_id}", summary="Delete a post")
async def delete_post(post_id: str, user: CurrentUser):
    return await SocialController.delete_post(post_id, user)


@router.post(
    "/posts/{post_id}/like",
    response_model=ToggleLikeResponse,
    summary="Like or unlike a post",
)
async def toggle_like(post_id: str, user: CurrentUser):
    return await SocialController.toggle_like(post_id, user)


@router.post(
    "/posts/{post_id}/save",
    response_model=ToggleSaveResponse,
    summary="Bookmark or unbookmark a post",
)
async def toggle_save(post_id: str, user: CurrentUser):
    return await SocialController.toggle_save(post_id, user)


@router.post(
    "/posts/{post_id}/report",
    response_model=ReportPostResponse,
    summary="Report a post",
)
async def report_post(
    post_id: str, payload: ReportPostRequest, user: CurrentUser
):
    return await SocialController.report_post(post_id, payload, user)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    summary="Add a comment to a post",
)
async def create_comment(
    post_id: str, payload: CreateCommentRequest, user: CurrentUser
):
    return await SocialController.create_comment(post_id, payload, user)


@router.get(
    "/posts/{post_id}/comments",
    response_model=CommentListResponse,
    summary="List comments on a post",
)
async def list_comments(
    post_id: str,
    user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await SocialController.list_comments(post_id, skip=skip, limit=limit)


@router.delete("/comments/{comment_id}", summary="Delete a comment")
async def delete_comment(comment_id: str, user: CurrentUser):
    return await SocialController.delete_comment(comment_id, user)


@router.post("/follow/{user_id}", summary="Follow a user")
async def follow_user(user_id: str, user: CurrentUser):
    return await SocialController.follow_user(user_id, user)


@router.post("/unfollow/{user_id}", summary="Unfollow a user")
async def unfollow_user(user_id: str, user: CurrentUser):
    return await SocialController.unfollow_user(user_id, user)


@router.get("/following", summary="List users followed by current user")
async def list_following(
    user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await SocialController.list_following(user, skip=skip, limit=limit)
