"""Messaging controller."""
from app.database import get_db
from app.models.user import UserDocument
from app.schemas.messaging import CreateConversationRequest, SendMessageRequest
from app.services.messaging_service import MessagingService


class MessagingController:
    @staticmethod
    async def start_conversation(
        payload: CreateConversationRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        return MessagingService(db).get_or_create_conversation(
            user_id_a=str(user["_id"]),
            user_id_b=payload.recipient_id,
        )

    @staticmethod
    async def list_conversations(
        user: UserDocument, skip: int = 0, limit: int = 30
    ) -> dict:
        db = get_db()
        return MessagingService(db).list_conversations(
            user_id=str(user["_id"]),
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def send_message(
        conversation_id: str, payload: SendMessageRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        return MessagingService(db).send_message(
            conversation_id=conversation_id,
            sender_id=str(user["_id"]),
            sender_name=user.get("name", "User"),
            content=payload.content,
        )

    @staticmethod
    async def list_messages(
        conversation_id: str, user: UserDocument, skip: int = 0, limit: int = 50
    ) -> dict:
        db = get_db()
        return MessagingService(db).list_messages(
            conversation_id=conversation_id,
            user_id=str(user["_id"]),
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def mark_read(conversation_id: str, user: UserDocument) -> dict:
        db = get_db()
        return MessagingService(db).mark_read(
            conversation_id=conversation_id,
            user_id=str(user["_id"]),
        )
