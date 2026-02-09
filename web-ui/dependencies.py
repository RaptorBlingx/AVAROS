"""Shared FastAPI dependencies for Web UI routers."""

from __future__ import annotations

from skill.services.settings import SettingsService


def get_settings_service() -> SettingsService:
    """Provide a SettingsService instance for request handlers."""
    return SettingsService()

