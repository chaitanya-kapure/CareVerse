"""Router registry.

Every feature module registers here. Adding a new router should be a
one-line change in this file, so the API surface can be read at a glance.
"""

from fastapi import APIRouter

from app.routes import auth, health

# Phase 2/3 routers are added here as they are built:
#   from app.routes import patients, documents, summary, access
#   api_router.include_router(patients.router)
#   api_router.include_router(documents.router)
#   api_router.include_router(summary.router)
#   api_router.include_router(access.router)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)

__all__ = ["api_router"]
