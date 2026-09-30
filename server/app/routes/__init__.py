"""Router registry.

Every feature module registers here. Adding a new router should be a
one-line change in this file, so the API surface can be read at a glance.
"""

from fastapi import APIRouter

from app.routes import access, auth, documents, doctor, health, patients

# Phase 4 adds the summary router here, when the AI summary exists:
#   from app.routes import summary
#   api_router.include_router(summary.router)

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

__all__ = ["api_router"]
