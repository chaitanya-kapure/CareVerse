"""Access request service — doctor requests, patient approves or rejects."""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.access import PatientAccessDocument
from app.models.access_request import (
    AccessRequestDocument,
    serialize_access_request,
)
from app.models.collections import (
    get_access_requests,
    get_patient_access,
    get_users,
)
from app.services.careverse_id_service import CareVerseIdService
from app.services.notification_service import NotificationService
from app.utils import errors

logger = logging.getLogger(__name__)


class AccessRequestService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._requests = get_access_requests(db)
        self._access = get_patient_access(db)
        self._users = get_users(db)
        self._id_service = CareVerseIdService(db)
        self._notifs = NotificationService(db)

    def create_request(
        self,
        doctor_id: str,
        doctor_name: str,
        careverse_id: str,
        purpose: str,
        categories: Optional[list[str]] = None,
        duration_days: int = 30,
        db: Optional[Database] = None,
    ) -> dict:
        """Doctor requests access to a patient's records using their CareVerse ID."""
        patient_id = self._id_service.lookup_patient_id(careverse_id.strip())
        if not patient_id:
            raise errors.not_found(
                "Patient with this CareVerse ID was not found",
                code="PATIENT_NOT_FOUND",
            )

        if doctor_id == patient_id:
            raise errors.bad_request(
                "Cannot request access to your own records as a doctor",
                code="SELF_REQUEST_NOT_ALLOWED",
            )

        # Check existing active access
        active_grant = self._access.find_one(
            {"doctor_id": doctor_id, "patient_id": patient_id, "status": "active"}
        )
        if active_grant:
            raise errors.conflict(
                "You already have active access to this patient's records",
                code="ACCESS_ALREADY_GRANTED",
            )

        # Check existing pending request
        existing_pending = self._requests.find_one(
            {"doctor_id": doctor_id, "patient_id": patient_id, "status": "pending"}
        )
        if existing_pending:
            raise errors.conflict(
                "A pending request for this patient already exists",
                code="REQUEST_ALREADY_EXISTS",
            )

        now = datetime.now(timezone.utc)
        doc: AccessRequestDocument = {
            "doctor_id": doctor_id,
            "doctor_name": doctor_name or "Doctor",
            "patient_careverse_id": careverse_id.strip(),
            "patient_id": patient_id,
            "purpose": (purpose or "").strip(),
            "requested_categories": categories or [],
            "requested_duration_days": duration_days,
            "status": "pending",
            "rejection_reason": None,
            "grant_id": None,
            "created_at": now,
            "responded_at": None,
        }

        res = self._requests.insert_one(doc)
        doc["_id"] = res.inserted_id

        # Notify patient
        self._notifs.send(
            user_id=patient_id,
            notif_type="access_request_received",
            title="New Access Request",
            body=f"{doctor_name} has requested access to your medical records.",
            payload={
                "request_id": str(doc["_id"]),
                "doctor_id": doctor_id,
                "purpose": purpose,
            },
        )

        return serialize_access_request(doc)

    def list_received(
        self, patient_id: str, skip: int = 0, limit: int = 20
    ) -> dict:
        """List access requests received by the patient."""
        filter_q = {"patient_id": patient_id}
        total = self._requests.count_documents(filter_q)
        cursor = (
            self._requests.find(filter_q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [serialize_access_request(r) for r in cursor]
        return {"items": items, "total": total}

    def list_sent(self, doctor_id: str, skip: int = 0, limit: int = 20) -> dict:
        """List access requests sent by the doctor."""
        filter_q = {"doctor_id": doctor_id}
        total = self._requests.count_documents(filter_q)
        cursor = (
            self._requests.find(filter_q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [serialize_access_request(r) for r in cursor]
        return {"items": items, "total": total}

    def approve(
        self, request_id: str, patient_id: str, db: Optional[Database] = None
    ) -> dict:
        """Patient approves doctor's access request, creating active grant."""
        if not ObjectId.is_valid(request_id):
            raise errors.not_found(
                "Access request not found", code="ACCESS_REQUEST_NOT_FOUND"
            )

        req = self._requests.find_one(
            {"_id": ObjectId(request_id), "patient_id": patient_id}
        )
        if not req:
            raise errors.not_found(
                "Access request not found", code="ACCESS_REQUEST_NOT_FOUND"
            )

        if req.get("status") != "pending":
            raise errors.bad_request(
                f"Cannot approve request with status '{req.get('status')}'",
                code="INVALID_REQUEST_STATUS",
            )

        now = datetime.now(timezone.utc)
        doctor_id = req["doctor_id"]

        # Create live grant in patient_access
        grant_doc: PatientAccessDocument = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "status": "active",
            "granted_at": now,
            "revoked_at": None,
            "note": f"Approved request: {req.get('purpose', '')}".strip() or None,
        }

        try:
            grant_res = self._access.insert_one(grant_doc)
            grant_id = str(grant_res.inserted_id)
        except DuplicateKeyError:
            existing = self._access.find_one(
                {"patient_id": patient_id, "doctor_id": doctor_id, "status": "active"}
            )
            grant_id = str(existing["_id"]) if existing else None

        self._requests.update_one(
            {"_id": ObjectId(request_id)},
            {
                "$set": {
                    "status": "approved",
                    "grant_id": grant_id,
                    "responded_at": now,
                }
            },
        )
        updated = self._requests.find_one({"_id": ObjectId(request_id)})

        # Notify doctor
        self._notifs.send(
            user_id=doctor_id,
            notif_type="access_approved",
            title="Access Request Approved",
            body="A patient has approved your medical records access request.",
            payload={"request_id": request_id, "grant_id": grant_id, "patient_id": patient_id},
        )

        return serialize_access_request(updated)

    def reject(
        self, request_id: str, patient_id: str, reason: Optional[str] = None
    ) -> dict:
        """Patient rejects doctor's access request."""
        if not ObjectId.is_valid(request_id):
            raise errors.not_found(
                "Access request not found", code="ACCESS_REQUEST_NOT_FOUND"
            )

        req = self._requests.find_one(
            {"_id": ObjectId(request_id), "patient_id": patient_id}
        )
        if not req:
            raise errors.not_found(
                "Access request not found", code="ACCESS_REQUEST_NOT_FOUND"
            )

        if req.get("status") != "pending":
            raise errors.bad_request(
                f"Cannot reject request with status '{req.get('status')}'",
                code="INVALID_REQUEST_STATUS",
            )

        now = datetime.now(timezone.utc)
        self._requests.update_one(
            {"_id": ObjectId(request_id)},
            {
                "$set": {
                    "status": "rejected",
                    "rejection_reason": (reason or "").strip() or None,
                    "responded_at": now,
                }
            },
        )
        updated = self._requests.find_one({"_id": ObjectId(request_id)})

        # Notify doctor
        self._notifs.send(
            user_id=req["doctor_id"],
            notif_type="access_rejected",
            title="Access Request Rejected",
            body="Your medical records access request was declined.",
            payload={"request_id": request_id, "reason": reason},
        )

        return serialize_access_request(updated)
