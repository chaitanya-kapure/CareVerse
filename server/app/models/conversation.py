"""conversations + messages collections."""
from datetime import datetime
from typing import Optional, TypedDict


class ConversationDocument(TypedDict, total=False):
    _id: object
    participant_ids: list       # list[str] exactly 2 user_ids, sorted
    created_at: datetime
    last_message_at: Optional[datetime]
    last_message_preview: Optional[str]


class MessageDocument(TypedDict, total=False):
    _id: object
    conversation_id: str
    sender_id: str
    sender_name: str
    content: str
    read_by: list               # list[str] user_ids
    created_at: datetime


def serialize_conversation(conv: ConversationDocument, other_participant_name: str = "", unread_count: int = 0) -> dict:
    return {
        "id": str(conv["_id"]),
        "participant_ids": conv.get("participant_ids") or [],
        "other_participant_name": other_participant_name,
        "last_message_at": conv.get("last_message_at"),
        "last_message_preview": conv.get("last_message_preview"),
        "unread_count": unread_count,
        "created_at": conv.get("created_at"),
    }


def serialize_message(msg: MessageDocument) -> dict:
    return {
        "id": str(msg["_id"]),
        "conversation_id": msg.get("conversation_id"),
        "sender_id": msg.get("sender_id"),
        "sender_name": msg.get("sender_name", ""),
        "content": msg.get("content", ""),
        "read_by": msg.get("read_by") or [],
        "created_at": msg.get("created_at"),
    }
