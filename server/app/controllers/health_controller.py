"""Health controller.

`/health` reports the real database state rather than a hardcoded "ok", so a
demo where Mongo is down is visibly broken instead of silently lying.
"""

from app.config import settings


class HealthController:
    @staticmethod
    def status(database_connected: bool) -> dict:
        return {
            "status": "ok" if database_connected else "degraded",
            "database": "connected" if database_connected else "unavailable",
            "environment": settings.environment,
            # Reported so a demo can show which summarizer is actually active.
            "ai_provider": settings.ai_provider if settings.ai_enabled else "mock",
        }

    @staticmethod
    def root() -> dict:
        return {
            "name": settings.app_name,
            "status": "ok",
            "docs": "/docs",
        }
