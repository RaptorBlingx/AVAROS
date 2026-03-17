"""Pytest configuration and shared fixtures for AVAROS tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from skill.services.settings import Base, SettingsService


def build_test_settings_service(
    database_url: str = "sqlite:///:memory:",
) -> SettingsService:
    """Create an initialised SettingsService for tests.

    For in-memory SQLite the engine is wired with ``StaticPool`` so the
    single connection is shared across threads (needed by FastAPI
    TestClient).  For on-disk URLs the normal ``initialize()`` path is
    used instead.

    Args:
        database_url: SQLAlchemy database URL.  Defaults to in-memory
            SQLite.

    Returns:
        Ready-to-use SettingsService instance.  Caller is responsible
        for calling ``close()`` when done.
    """
    if database_url == "sqlite:///:memory:":
        svc = SettingsService()
        engine = create_engine(
            database_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        svc._engine = engine
        svc._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        Base.metadata.create_all(engine)
        svc._initialized = True
        return svc

    svc = SettingsService(database_url=database_url)
    svc.initialize()
    return svc


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Provides a test configuration for testing"""
    return {
        "platform_type": "reneryo",
        "api_url": "http://localhost:8000",
        "api_key": "test_key",
        "timeout": 30,
        "max_retries": 3
    }


@pytest.fixture
def mock_kpi_data() -> Dict[str, Any]:
    """Provides mock KPI data for testing"""
    return {
        "metric": "energy_per_unit",
        "value": 45.2,
        "unit": "kWh/unit",
        "timestamp": datetime.now().isoformat(),
        "asset_id": "compressor-1",
        "period": "today"
    }


@pytest.fixture
def mock_trend_data() -> Dict[str, Any]:
    """Provides mock trend data for testing"""
    base_time = datetime.now()
    return {
        "metric": "scrap_rate",
        "data_points": [
            {"timestamp": (base_time - timedelta(days=i)).isoformat(), "value": 3.1 + i * 0.1}
            for i in range(7)
        ],
        "trend_direction": "up",
        "change_percent": 12.5
    }


@pytest.fixture
def mock_comparison_data() -> Dict[str, Any]:
    """Provides mock comparison data for testing"""
    return {
        "metric": "energy_per_unit",
        "items": [
            {"id": "compressor-1", "value": 45.2, "unit": "kWh/unit"},
            {"id": "compressor-2", "value": 52.3, "unit": "kWh/unit"}
        ],
        "winner_id": "compressor-1",
        "winner_value": 45.2
    }


@pytest.fixture
def mock_anomaly_data() -> Dict[str, Any]:
    """Provides mock anomaly data for testing"""
    return {
        "is_anomalous": True,
        "anomalies": [
            {
                "timestamp": datetime.now().isoformat(),
                "value": 67.8,
                "expected": 45.2,
                "deviation_sigma": 3.2
            }
        ],
        "severity": "WARNING",
        "recommendation": "Check compressor load pattern"
    }


@pytest.fixture
def mock_whatif_data() -> Dict[str, Any]:
    """Provides mock what-if scenario data for testing"""
    return {
        "scenario_id": "temperature_reduction",
        "baseline": {"value": 45.2, "unit": "kWh/unit"},
        "projected": {"value": 42.1, "unit": "kWh/unit"},
        "delta": -3.1,
        "delta_percent": -6.86,
        "confidence": 0.85
    }
