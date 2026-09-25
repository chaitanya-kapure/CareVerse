"""Schemas shared by more than one router."""

from typing import Any, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str
    ai_provider: str


class ApiError(BaseModel):
    """The single error shape used across the API."""

    detail: str
    code: Optional[str] = None


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class Page(BaseModel):
    items: list[Any]
    meta: PageMeta
