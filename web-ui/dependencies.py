"""Shared FastAPI dependencies for Web UI routers."""

from __future__ import annotations

from fastapi import Header, HTTPException

from config import WEB_API_KEY
from skill.services.settings import SettingsService


def get_settings_service() -> SettingsService:
    """Provide a SettingsService instance for request handlers."""
    return SettingsService()


def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Validate ``X-API-Key`` header against the configured key.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 when the key is missing or invalid.
    """
    if x_api_key != WEB_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key

