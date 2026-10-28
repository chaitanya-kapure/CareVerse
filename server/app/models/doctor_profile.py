"""doctor_profiles collection — one per doctor user."""
from datetime import datetime
from typing import Literal, Optional, TypedDict

VerificationStatus = Literal["unverified", "pending", "verified", "rejected"]


class DoctorProfileDocument(TypedDict, total=False):
    _id: object
    user_id: str                    # -> users._id, unique
    specialty: str
    qualifications: str             # free text, e.g. "MBBS, MD"
    experience_years: Optional[int]
    bio: str
    location: Optional[str]
    verification_status: VerificationStatus
    profile_image_url: Optional[str]
    follower_count: int
    post_count: int
    created_at: datetime
    updated_at: datetime


def serialize_doctor_profile(profile: DoctorProfileDocument, user_name: str = "") -> dict:
    return {
        "id": str(profile["_id"]),
        "user_id": profile.get("user_id"),
        "name": user_name,
        "specialty": profile.get("specialty", ""),
        "qualifications": profile.get("qualifications", ""),
        "experience_years": profile.get("experience_years"),
        "bio": profile.get("bio", ""),
        "location": profile.get("location"),
        "verification_status": profile.get("verification_status", "unverified"),
        "profile_image_url": profile.get("profile_image_url"),
        "follower_count": profile.get("follower_count", 0),
        "post_count": profile.get("post_count", 0),
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
    }
