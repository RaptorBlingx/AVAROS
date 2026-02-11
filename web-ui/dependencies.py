"""Shared FastAPI dependencies for Web UI routers."""

from __future__ import annotations

from skill.services.kpi_measurement import KPIMeasurementService
from skill.services.production_data import ProductionDataService
from skill.services.settings import SettingsService


def get_settings_service() -> SettingsService:
    """Provide a SettingsService instance for request handlers."""
    return SettingsService()


def get_production_data_service() -> ProductionDataService:
    """Provide a ProductionDataService instance for request handlers."""
    return ProductionDataService()


def get_kpi_measurement_service() -> KPIMeasurementService:
    """Provide a KPIMeasurementService instance for request handlers."""
    return KPIMeasurementService()





