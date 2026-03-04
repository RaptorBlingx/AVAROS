"""Shared FastAPI dependencies for Web UI routers."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from skill.adapters.factory import AdapterFactory
from skill.services.kpi_measurement import KPIMeasurementService
from skill.services.production_data import ProductionDataService
from skill.services.settings import SettingsService
from services.kpi_collector import KPICollector
from services.kpi_scheduler import KPIScheduler


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsService:
    """Provide a cached, initialized SettingsService for request handlers."""
    service = SettingsService()
    service.initialize()
    return service


def get_adapter_factory(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AdapterFactory:
    """Provide an AdapterFactory bound to the current SettingsService.

    Args:
        settings_service: Request-scoped settings provider.

    Returns:
        AdapterFactory configured to read active profile settings.
    """
    return AdapterFactory(settings_service=settings_service)


def get_production_data_service() -> ProductionDataService:
    """Provide a ProductionDataService instance for request handlers."""
    return ProductionDataService()


def get_kpi_measurement_service() -> KPIMeasurementService:
    """Provide a KPIMeasurementService instance for request handlers."""
    return KPIMeasurementService()


@lru_cache(maxsize=1)
def get_kpi_scheduler() -> KPIScheduler:
    """Provide a cached KPI scheduler instance for app lifecycle hooks."""
    collector = KPICollector(
        settings_service=get_settings_service(),
        kpi_service=get_kpi_measurement_service(),
    )
    return KPIScheduler(collector=collector)



