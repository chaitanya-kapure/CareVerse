"""System endpoints. Kept thin; status logic lives in the controller."""

from fastapi import APIRouter

from app.controllers.health_controller import HealthController
from app.database import mongo
from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="API and database health")
async def health():
    return HealthController.status(mongo.ping())


@router.get("/", include_in_schema=False)
async def root():
    return HealthController.root()
