"""Router registry.

Every feature module registers here. Adding a new router should be a
one-line change in this file, so the API surface can be read at a glance.
"""

from fastapi import APIRouter

from app.routes import (
    access,
    access_requests,
    auth,
    discovery,
    doctor,
    doctor_profile,
    documents,
    health,
    messaging,
    notifications,
    patients,
    social,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(documents.router)
api_router.include_router(access.router)
api_router.include_router(doctor.router)

# New feature routers
api_router.include_router(doctor_profile.router)
api_router.include_router(access_requests.router)
api_router.include_router(social.router)
api_router.include_router(messaging.router)
api_router.include_router(notifications.router)
api_router.include_router(discovery.router)

__all__ = ["api_router"]
