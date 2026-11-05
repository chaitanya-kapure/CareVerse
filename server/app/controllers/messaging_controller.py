"""Messaging controller."""
from bson import ObjectId

from app.database import get_db
from app.middlewares.auth_middleware import assert_patient_access
from app.models.collections import get_users
from app.models.user import UserDocument
from app.schemas.messaging import CreateConversationRequest, SendMessageRequest
from app.services.careverse_id_service import CareVerseIdService
from app.services.messaging_service import MessagingService
from app.utils import errors


class MessagingController:
    @staticmethod
    async def start_conversation(
        payload: CreateConversationRequest, user: UserDocument
    ) -> dict:
        db = get_db()
        recipient_id = payload.recipient_id
        if len(recipient_id) == 4:
            recipient_id = CareVerseIdService(db).lookup_patient_id(recipient_id)
            if recipient_id is None:
                raise errors.not_found(
                    "Patient with this CareVerse ID was not found",
                    code="PATIENT_NOT_FOUND",
                )

        recipient = get_users(db).find_one({"_id": ObjectId(recipient_id)})
        if recipient is None:
            raise errors.not_found("User not found", code="USER_NOT_FOUND")

        # A conversation is only available between a patient and a clinician
        # with an active patient-approved grant. Reuse the canonical access
        # check whichever participant initiated the conversation.
        if user.get("role") == "doctor" and recipient.get("role") == "patient":
            assert_patient_access(db, user, str(recipient["_id"]))
        elif user.get("role") == "patient" and recipient.get("role") == "doctor":
            assert_patient_access(db, recipient, str(user["_id"]))
        else:
            raise errors.forbidden(
                "Conversations are available between patients and authorized clinicians",
                code="CONVERSATION_CONTACT_NOT_ALLOWED",
            )

        return MessagingService(db).get_or_create_conversation(
            user_id_a=str(user["_id"]),
            user_id_b=str(recipient["_id"]),
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
