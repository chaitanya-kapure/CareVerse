"""Messaging service — direct conversations and messages."""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database

from app.models.collections import (
    get_conversations,
    get_messages,
    get_users,
)
from app.models.conversation import (
    ConversationDocument,
    MessageDocument,
    serialize_conversation,
    serialize_message,
)
from app.services.notification_service import NotificationService
from app.utils import errors

logger = logging.getLogger(__name__)


class MessagingService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._conversations = get_conversations(db)
        self._messages = get_messages(db)
        self._users = get_users(db)
        self._notifs = NotificationService(db)

    def get_or_create_conversation(self, user_id_a: str, user_id_b: str) -> dict:
        """Find an existing 1-on-1 conversation or create one."""
        if user_id_a == user_id_b:
            raise errors.bad_request(
                "Cannot start a conversation with yourself",
                code="SELF_CONVERSATION_NOT_ALLOWED",
            )

        if not ObjectId.is_valid(user_id_b):
            raise errors.not_found("User not found", code="USER_NOT_FOUND")

        target_user = self._users.find_one({"_id": ObjectId(user_id_b)})
        if not target_user:
            raise errors.not_found("User not found", code="USER_NOT_FOUND")

        pair = sorted([user_id_a, user_id_b])
        conv = self._conversations.find_one({"participant_ids": pair})
        if not conv:
            now = datetime.now(timezone.utc)
            new_doc: ConversationDocument = {
                "participant_ids": pair,
                "created_at": now,
                "last_message_at": None,
                "last_message_preview": None,
            }
            res = self._conversations.insert_one(new_doc)
            new_doc["_id"] = res.inserted_id
            conv = new_doc

        return self._format_conversation(conv, viewer_id=user_id_a)

    def list_conversations(self, user_id: str, skip: int = 0, limit: int = 30) -> dict:
        """List all conversations for a user, sorted by last message time."""
        filter_q = {"participant_ids": user_id}
        total = self._conversations.count_documents(filter_q)
        cursor = (
            self._conversations.find(filter_q)
            .sort("last_message_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [self._format_conversation(c, viewer_id=user_id) for c in cursor]
        return {"items": items, "total": total}

    def send_message(
        self,
        conversation_id: str,
        sender_id: str,
        sender_name: str,
        content: str,
    ) -> dict:
        """Send a message to a conversation."""
        conv = self._require_conversation_member(conversation_id, sender_id)

        clean_content = content.strip()
        if not clean_content:
            raise errors.bad_request("Message content cannot be empty", code="EMPTY_MESSAGE")

        now = datetime.now(timezone.utc)
        msg_doc: MessageDocument = {
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "sender_name": sender_name or "User",
            "content": clean_content,
            "read_by": [sender_id],
            "created_at": now,
        }

        res = self._messages.insert_one(msg_doc)
        msg_doc["_id"] = res.inserted_id

        preview = (clean_content[:97] + "...") if len(clean_content) > 100 else clean_content
        self._conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$set": {
                    "last_message_at": now,
                    "last_message_preview": preview,
                }
            },
        )

        # Notify other participant
        recipient_id = [p for p in conv.get("participant_ids", []) if p != sender_id]
        if recipient_id:
            self._notifs.send(
                user_id=recipient_id[0],
                notif_type="new_message",
                title="New Message",
                body=f"{sender_name}: {preview}",
                payload={"conversation_id": conversation_id, "message_id": str(msg_doc["_id"])},
            )

        return serialize_message(msg_doc)

    def list_messages(
        self,
        conversation_id: str,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """List messages in a conversation."""
        self._require_conversation_member(conversation_id, user_id)

        filter_q = {"conversation_id": conversation_id}
        total = self._messages.count_documents(filter_q)
        cursor = (
            self._messages.find(filter_q)
            .sort("created_at", 1)
            .skip(skip)
            .limit(limit)
        )
        items = [serialize_message(m) for m in cursor]
        return {"items": items, "total": total}

    def mark_read(self, conversation_id: str, user_id: str) -> dict:
        """Mark unread messages in a conversation as read by user."""
        self._require_conversation_member(conversation_id, user_id)

        self._messages.update_many(
            {"conversation_id": conversation_id, "read_by": {"$ne": user_id}},
            {"$addToSet": {"read_by": user_id}},
        )
        return {"marked": True}

    def _require_conversation_member(self, conversation_id: str, user_id: str) -> dict:
        if not ObjectId.is_valid(conversation_id):
            raise errors.not_found("Conversation not found", code="CONVERSATION_NOT_FOUND")

        conv = self._conversations.find_one({"_id": ObjectId(conversation_id)})
        if not conv:
            raise errors.not_found("Conversation not found", code="CONVERSATION_NOT_FOUND")

        if user_id not in conv.get("participant_ids", []):
            raise errors.forbidden(
                "You are not a participant in this conversation",
                code="FORBIDDEN_CONVERSATION",
            )
        return conv

    def _format_conversation(self, conv: dict, viewer_id: str) -> dict:
        participant_ids = conv.get("participant_ids", [])
        other_ids = [p for p in participant_ids if p != viewer_id]
        other_id = other_ids[0] if other_ids else ""
        other_name = ""
        if other_id and ObjectId.is_valid(other_id):
            u = self._users.find_one({"_id": ObjectId(other_id)})
            if u:
                other_name = u.get("name", "")

        unread_count = self._messages.count_documents(
            {
                "conversation_id": str(conv["_id"]),
                "sender_id": {"$ne": viewer_id},
                "read_by": {"$ne": viewer_id},
            }
        )
        return serialize_conversation(
            conv, other_participant_name=other_name, unread_count=unread_count
        )
