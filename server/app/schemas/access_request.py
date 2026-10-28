"""Schemas for doctor-initiated access requests."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateAccessRequestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    careverse_id: str = Field(min_length=4, max_length=4)
    purpose: str = Field(min_length=1, max_length=500)
    categories: Optional[list[str]] = Field(default_factory=list)
    duration_days: int = Field(default=30, ge=1, le=365)


class ApproveAccessRequestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    note: Optional[str] = Field(default=None, max_length=500)


class RejectAccessRequestRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: Optional[str] = Field(default=None, max_length=500)


class AccessRequestResponse(BaseModel):
    id: str
    doctor_id: Optional[str] = None
    doctor_name: str = ""
    patient_careverse_id: Optional[str] = None
    patient_id: Optional[str] = None
    purpose: str = ""
    requested_categories: list[str] = []
    requested_duration_days: int = 30
    status: str = "pending"
    rejection_reason: Optional[str] = None
    grant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None


class AccessRequestListResponse(BaseModel):
    items: list[AccessRequestResponse]
    total: int
