"""Schemas for doctor profiles and doctor discovery."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DoctorProfileResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str = ""
    specialty: str = ""
    qualifications: str = ""
    experience_years: Optional[int] = None
    bio: str = ""
    location: Optional[str] = None
    verification_status: str = "unverified"
    profile_image_url: Optional[str] = None
    follower_count: int = 0
    post_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DoctorProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    specialty: Optional[str] = Field(default=None, max_length=100)
    qualifications: Optional[str] = Field(default=None, max_length=200)
    experience_years: Optional[int] = Field(default=None, ge=0, le=70)
    bio: Optional[str] = Field(default=None, max_length=2000)
    location: Optional[str] = Field(default=None, max_length=100)
    profile_image_url: Optional[str] = Field(default=None, max_length=500)


class DoctorDiscoveryResponse(BaseModel):
    items: list[DoctorProfileResponse]
    total: int
