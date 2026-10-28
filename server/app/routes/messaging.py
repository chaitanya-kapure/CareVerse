"""Messaging routes."""
from fastapi import APIRouter, Query

from app.controllers.messaging_controller import MessagingController
from app.middlewares.auth_middleware import CurrentUser
from app.schemas.messaging import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MarkReadResponse,
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
)

router = APIRouter(prefix="/conversations", tags=["messaging"])


@router.post(
    "",
    response_model=ConversationResponse,
    summary="Get or create a conversation with a recipient",
)
async def start_conversation(
    payload: CreateConversationRequest, user: CurrentUser
):
    return await MessagingController.start_conversation(payload, user)


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List all conversations for authenticated user",
)
async def list_conversations(
    user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
):
    return await MessagingController.list_conversations(user, skip=skip, limit=limit)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    summary="Send a message in a conversation",
)
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    user: CurrentUser,
):
    return await MessagingController.send_message(conversation_id, payload, user)


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="List messages in a conversation",
)
async def list_messages(
    conversation_id: str,
    user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await MessagingController.list_messages(
        conversation_id, user, skip=skip, limit=limit
    )


@router.post(
    "/{conversation_id}/read",
    response_model=MarkReadResponse,
    summary="Mark messages in a conversation as read",
)
async def mark_read(
    conversation_id: str,
    user: CurrentUser,
):
    return await MessagingController.mark_read(conversation_id, user)
