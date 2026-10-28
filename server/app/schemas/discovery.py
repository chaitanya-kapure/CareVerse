"""Discovery schemas."""
from typing import Optional

from pydantic import BaseModel


class PatientDiscoveryResponse(BaseModel):
    """Minimal, non-clinical patient lookup response."""
    patient_id: str
    careverse_id: str
    full_name: str
    gender: Optional[str] = "unspecified"
