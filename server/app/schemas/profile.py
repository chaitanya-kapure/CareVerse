"""Patient profile schemas.

The profile is deliberately small: name, date of birth, contact details and
the patient's own free-text notes. It carries no derived, inferred or
predicted health information -- every field here was typed by the patient.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

GENDERS = ("male", "female", "other", "unspecified")


def _check_iso_date(value: Optional[str], field: str) -> Optional[str]:
    """Accept an ISO calendar date, or empty/None for "not provided"."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) != 10 or trimmed[4] != "-" or trimmed[7] != "-":
        raise ValueError(f"{field} must be an ISO date in the form YYYY-MM-DD")
    try:
        year, month, day = (int(part) for part in trimmed.split("-"))
        # `date` rather than a string comparison, so a plausible-looking but
        # impossible date like 2026-02-30 is rejected instead of accepted.
        date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"{field} is not a real calendar date") from exc
    if year < 1900 or year > 2100:
        raise ValueError(f"{field} is outside the supported range")
    return trimmed


class PatientProfileUpdate(BaseModel):
    """Optional-by-design PATCH body.

    Every field defaults to None and downstream uses
    `model_dump(exclude_unset=True)`, so a client that sends only
    `{"phone": "..."}` leaves the rest of the profile untouched. Sending an
    explicit `null` clears a field; omitting it does not.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    date_of_birth: Optional[str] = Field(default=None, max_length=10)
    gender: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    address: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("date_of_birth")
    @classmethod
    def _validate_dob(cls, value: Optional[str]) -> Optional[str]:
        return _check_iso_date(value, "Date of birth")

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value not in GENDERS:
            raise ValueError(f"Gender must be one of {', '.join(GENDERS)}")
        return value

    # `full_name` needs no validator beyond `min_length` + the model-level
    # `str_strip_whitespace`, which turns "   " into "" before length is
    # checked. A custom validator here would only restate that.


class PatientProfileResponse(BaseModel):
    """Mirror of `serialize_profile` in models/patient_profile.py."""

    id: str
    patient_id: str
    full_name: str
    date_of_birth: Optional[str] = None
    gender: str = "unspecified"
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
