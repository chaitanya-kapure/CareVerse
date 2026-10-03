"""Router registry.

Every feature module registers here. Adding a new router should be a
one-line change in this file, so the API surface can be read at a glance.
"""

from fastapi import APIRouter

from app.routes import access, auth, documents, doctor, health, patients

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
# `patients` and `documents` overlap on purpose: the profile lives at
# /patients/me and the record list at /patients/me/documents. Distinct
# full paths, so the registry stays readable.
api_router.include_router(patients.router)
api_router.include_router(documents.router)
# Phase 3: the patient manages who can read their records, and the doctor
# reads only those. `access` is mounted under /patients/me because granting
# is something a patient does to their own account.
api_router.include_router(access.router)
api_router.include_router(doctor.router)

# Phase 4B: the summary is not a separate router. `/patients/me/summary` and
# `/doctor/patients/{patientId}/summary` hang off the two routers that already
# declare the matching role dependency and already prove access to the patient,
# so adding it here would mean a third place where that check could be skipped.

__all__ = ["api_router"]
