"""Schemas for messaging and conversations."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    recipient_id: str = Field(min_length=24, max_length=24)


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    content: str
    read_by: list[str] = []
    created_at: Optional[datetime] = None


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int


class ConversationResponse(BaseModel):
    id: str
    participant_ids: list[str] = []
    other_participant_name: str = ""
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    unread_count: int = 0
    created_at: Optional[datetime] = None


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int


class MarkReadResponse(BaseModel):
    marked: bool
