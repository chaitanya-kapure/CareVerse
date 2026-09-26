"""MongoDB connection management.

The previous implementation used module-level globals connected at import
time. That made the connection impossible to close cleanly and impossible to
inspect from the app lifespan. This exposes an explicit `MongoManager` that
FastAPI connects on startup and closes on shutdown.
"""

import logging
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import settings

logger = logging.getLogger(__name__)


class MongoManager:
    """Owns the MongoClient lifecycle for the whole process."""

    def __init__(self) -> None:
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None

    def connect(self) -> Optional[Database]:
        if self._client is not None:
            return self._db

        try:
            self._client = MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=5000,
                uuidRepresentation="standard",
                # PyMongo hands back naive datetimes unless asked otherwise,
                # while everything in this codebase writes `datetime.now(
                # timezone.utc)`. Comparing one against the other raises
                # TypeError, so any expiry check would blow up at runtime.
                # Reading back as aware UTC keeps writes and reads symmetric,
                # and makes serialized timestamps carry an explicit offset
                # instead of silently implying one.
                tz_aware=True,
            )
            self._client.admin.command("ping")
            self._db = self._client[settings.mongodb_db_name]
            logger.info("MongoDB connected: %s", settings.mongodb_db_name)
        except PyMongoError as exc:
            # The API still boots so /health can report the real reason
            # instead of the process crash-looping with an opaque stack trace.
            logger.error("MongoDB connection failed: %s", exc)
            self._client = None
            self._db = None

        return self._db

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            logger.info("MongoDB connection closed")
        self._client = None
        self._db = None

    def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    @property
    def db(self) -> Optional[Database]:
        return self._db


mongo = MongoManager()


def get_db() -> Database:
    """FastAPI dependency. Raises 503 when Mongo is unavailable.

    Every request that touches the database depends on this, so a downed
    database produces one consistent error instead of NoneType crashes.
    """
    from fastapi import HTTPException, status

    if mongo.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
            headers={"code": "DATABASE_UNAVAILABLE"},
        )
    return mongo.db
