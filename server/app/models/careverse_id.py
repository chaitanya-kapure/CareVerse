"""careverse_ids collection — maps patient_id to a unique 4-digit display ID."""
import secrets
from typing import TypedDict


class CareVerseIdDocument(TypedDict, total=False):
    _id: object
    patient_id: str      # -> users._id (role=patient), unique
    careverse_id: str    # exactly 4 digits with leading zeros, unique, e.g. "0047"


def format_careverse_id(n: int) -> str:
    return str(n).zfill(4)


def generate_candidate() -> str:
    """Cryptographically random 4-digit ID (0000-9999)."""
    return format_careverse_id(secrets.randbelow(10000))
