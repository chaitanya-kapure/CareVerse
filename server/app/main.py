"""CAREVERSE API entrypoint.

Layering:  route -> controller -> service -> model
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.config import settings  # noqa: E402  (must follow load_dotenv)
from app.database import mongo  # noqa: E402
from app.middlewares.error_handler import register_exception_handlers  # noqa: E402
from app.models.indexes import ensure_indexes  # noqa: E402
from app.routes import api_router  # noqa: E402

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# pymongo logs every topology heartbeat at DEBUG, which drowns out the
# application's own output during development.
for noisy in ("pymongo", "pymongo.topology", "pymongo.connection", "pymongo.serverSelection"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own the Mongo connection for the lifetime of the process."""
    db = mongo.connect()
    if db is not None:
        ensure_indexes(db)
    else:
        logger.warning("Starting without a database; data routes will return 503")
    yield
    mongo.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "CAREVERSE centralizes a patient's uploaded medical records and "
        "generates a traceable, AI-assisted summary of those records.\n\n"
        "**CAREVERSE is not a diagnostic system.** The summary is a "
        "summarization layer over documents the patient uploaded. It is not "
        "a diagnosis and must never be used as medical advice."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

register_exception_handlers(app)
app.include_router(api_router)
