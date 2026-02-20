"""
KPI Progress Router Test Suite

Covers all REST endpoints:
    - POST /api/v1/kpi/baseline → 201
    - GET /api/v1/kpi/baseline/{site_id} → list
    - DELETE /api/v1/kpi/baseline/{site_id}/{metric} → 200/404
    - POST /api/v1/kpi/snapshot → 201
    - GET /api/v1/kpi/snapshots/{site_id}/{metric} → list
    - GET /api/v1/kpi/progress/{site_id} → site progress
    - GET /api/v1/kpi/progress/{site_id}/{metric} → single
    - GET /api/v1/kpi/export/{site_id} → dataset
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add web-ui to path for imports
WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if WEB_UI_DIR not in sys.path:
    sys.path.insert(0, WEB_UI_DIR)

from fastapi.testclient import TestClient

from main import app  # noqa: E402
from config import WEB_API_KEY  # noqa: E402
from dependencies import (  # noqa: E402
    get_kpi_measurement_service,
    get_settings_service,
)
from skill.services.database import Base  # noqa: E402
from skill.domain.kpi_baseline import KPIBaseline, KPISnapshot  # noqa: E402
from skill.services.kpi_measurement import KPIMeasurementService  # noqa: E402
from skill.services.settings import SettingsService  # noqa: E402


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def kpi_service() -> KPIMeasurementService:
    """In-memory KPIMeasurementService with thread-safe StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    svc = KPIMeasurementService(database_url="sqlite:///:memory:")
    svc._engine = engine
    svc._session_factory = sessionmaker(
        bind=engine, expire_on_commit=False,
    )
    Base.metadata.create_all(engine)
    svc._initialized = True
    return svc


@pytest.fixture
def client(
    kpi_service: KPIMeasurementService,
) -> Generator[TestClient, None, None]:
    """Test client with dependency overrides and auth header."""
    test_settings = SettingsService()
    test_settings.initialize()

    app.dependency_overrides[get_settings_service] = lambda: test_settings
    app.dependency_overrides[get_kpi_measurement_service] = (
        lambda: kpi_service
    )

    with TestClient(app, headers={"X-API-Key": WEB_API_KEY}) as tc:
        yield tc

    app.dependency_overrides.clear()


BASELINE_PAYLOAD = {
    "metric": "energy_per_unit",
    "site_id": "artibilim",
    "value": 2.5,
    "unit": "kWh/unit",
    "period_start": "2026-01-01",
    "period_end": "2026-01-31",
}

SNAPSHOT_PAYLOAD = {
    "metric": "energy_per_unit",
    "site_id": "artibilim",
    "value": 2.2,
    "unit": "kWh/unit",
    "period_start": "2026-06-01",
    "period_end": "2026-06-30",
}


# ══════════════════════════════════════════════════════════
# POST — Baseline
# ══════════════════════════════════════════════════════════


class TestPostBaseline:
    """POST /api/v1/kpi/baseline."""

    def test_create_baseline_201(self, client: TestClient) -> None:
        """Valid payload returns 201 with baseline data."""
        resp = client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["metric"] == "energy_per_unit"
        assert data["baseline_value"] == 2.5
        assert data["site_id"] == "artibilim"

    def test_upsert_baseline_overwrites(self, client: TestClient) -> None:
        """Posting same metric+site updates the baseline."""
        client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        updated = {**BASELINE_PAYLOAD, "value": 2.3}
        resp = client.post("/api/v1/kpi/baseline", json=updated)
        assert resp.status_code == 201
        assert resp.json()["baseline_value"] == 2.3

    def test_create_baseline_validation(self, client: TestClient) -> None:
        """Missing required field → 422."""
        payload = {"metric": "energy_per_unit"}
        resp = client.post("/api/v1/kpi/baseline", json=payload)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# GET — Baselines
# ══════════════════════════════════════════════════════════


class TestGetBaselines:
    """GET /api/v1/kpi/baseline/{site_id}."""

    def test_list_baselines_empty(self, client: TestClient) -> None:
        """No baselines → empty list."""
        resp = client.get("/api/v1/kpi/baseline/artibilim")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_baselines_with_data(self, client: TestClient) -> None:
        """Created baselines appear in list."""
        client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        resp = client.get("/api/v1/kpi/baseline/artibilim")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["metric"] == "energy_per_unit"


# ══════════════════════════════════════════════════════════
# DELETE — Baseline
# ══════════════════════════════════════════════════════════


class TestDeleteBaseline:
    """DELETE /api/v1/kpi/baseline/{site_id}/{metric}."""

    def test_delete_existing(self, client: TestClient) -> None:
        """Delete existing baseline → 200."""
        client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        resp = client.delete(
            "/api/v1/kpi/baseline/artibilim/energy_per_unit",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_not_found(self, client: TestClient) -> None:
        """Delete non-existent baseline → 404."""
        resp = client.delete("/api/v1/kpi/baseline/fake/fake_metric")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# POST — Snapshot
# ══════════════════════════════════════════════════════════


class TestPostSnapshot:
    """POST /api/v1/kpi/snapshot."""

    def test_create_snapshot_201(self, client: TestClient) -> None:
        """Valid snapshot returns 201."""
        resp = client.post("/api/v1/kpi/snapshot", json=SNAPSHOT_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["metric"] == "energy_per_unit"
        assert data["value"] == 2.2

    def test_create_snapshot_validation(self, client: TestClient) -> None:
        """Missing required field → 422."""
        resp = client.post("/api/v1/kpi/snapshot", json={"metric": "x"})
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# GET — Snapshots
# ══════════════════════════════════════════════════════════


class TestGetSnapshots:
    """GET /api/v1/kpi/snapshots/{site_id}/{metric}."""

    def test_get_snapshots_empty(self, client: TestClient) -> None:
        """No snapshots → empty list."""
        resp = client.get(
            "/api/v1/kpi/snapshots/artibilim/energy_per_unit",
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_snapshots_with_data(self, client: TestClient) -> None:
        """Created snapshots appear in list."""
        client.post("/api/v1/kpi/snapshot", json=SNAPSHOT_PAYLOAD)
        resp = client.get(
            "/api/v1/kpi/snapshots/artibilim/energy_per_unit",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["value"] == 2.2


# ══════════════════════════════════════════════════════════
# GET — Progress (Single Metric)
# ══════════════════════════════════════════════════════════


class TestGetMetricProgress:
    """GET /api/v1/kpi/progress/{site_id}/{metric}."""

    def test_progress_with_baseline(self, client: TestClient) -> None:
        """Progress computed correctly with query params."""
        client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        resp = client.get(
            "/api/v1/kpi/progress/artibilim/energy_per_unit",
            params={"current_value": 2.2, "current_unit": "kWh/unit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["improvement_percent"] == 12.0
        assert data["target_met"] is True

    def test_progress_no_baseline_404(self, client: TestClient) -> None:
        """Progress without baseline → 404."""
        resp = client.get(
            "/api/v1/kpi/progress/artibilim/energy_per_unit",
            params={"current_value": 2.2, "current_unit": "kWh/unit"},
        )
        assert resp.status_code == 404

    def test_progress_missing_params_422(self, client: TestClient) -> None:
        """Missing required query params → 422."""
        resp = client.get(
            "/api/v1/kpi/progress/artibilim/energy_per_unit",
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# GET — Site Progress
# ══════════════════════════════════════════════════════════


class TestGetSiteProgress:
    """GET /api/v1/kpi/progress/{site_id}."""

    def test_site_progress_with_snapshots(
        self, client: TestClient,
    ) -> None:
        """Site progress uses latest snapshots as current values."""
        client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        client.post("/api/v1/kpi/snapshot", json=SNAPSHOT_PAYLOAD)

        resp = client.get("/api/v1/kpi/progress/artibilim")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "artibilim"
        assert data["baselines_count"] == 1
        assert len(data["progress"]) == 1
        assert data["progress"][0]["improvement_percent"] == 12.0

    def test_site_progress_empty(self, client: TestClient) -> None:
        """Site with no baselines returns zero counts."""
        resp = client.get("/api/v1/kpi/progress/artibilim")
        assert resp.status_code == 200
        data = resp.json()
        assert data["baselines_count"] == 0
        assert data["progress"] == []

    def test_site_progress_no_snapshots(
        self, client: TestClient,
    ) -> None:
        """Baselines without snapshots → no progress entries."""
        client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        resp = client.get("/api/v1/kpi/progress/artibilim")
        assert resp.status_code == 200
        data = resp.json()
        assert data["baselines_count"] == 1
        assert data["progress"] == []


# ══════════════════════════════════════════════════════════
# GET — Export
# ══════════════════════════════════════════════════════════


class TestExport:
    """GET /api/v1/kpi/export/{site_id}."""

    def test_export_with_data(self, client: TestClient) -> None:
        """Export returns anonymized baseline data."""
        client.post("/api/v1/kpi/baseline", json=BASELINE_PAYLOAD)
        resp = client.get("/api/v1/kpi/export/artibilim")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["metric"] == "energy_per_unit"
        assert "baseline_value" in data[0]
        assert "period_start" in data[0]

    def test_export_empty(self, client: TestClient) -> None:
        """Export for empty site returns empty list."""
        resp = client.get("/api/v1/kpi/export/nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []


class TestKpiServiceClearSiteData:
    """Service helper used by profile activation flow."""

    def test_clear_site_data_removes_baselines_and_snapshots(
        self,
        kpi_service: KPIMeasurementService,
    ) -> None:
        """clear_site_data deletes all KPI rows for a site."""
        kpi_service.record_baseline(
            KPIBaseline(
                metric="energy_per_unit",
                site_id="pilot-1",
                baseline_value=2.5,
                unit="kWh/unit",
                recorded_at=datetime.utcnow(),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
            )
        )
        kpi_service.record_snapshot(
            KPISnapshot(
                metric="energy_per_unit",
                site_id="pilot-1",
                value=2.2,
                unit="kWh/unit",
                measured_at=datetime.utcnow(),
                period_start=date(2026, 2, 1),
                period_end=date(2026, 2, 28),
            )
        )

        deleted_baselines, deleted_snapshots = kpi_service.clear_site_data("pilot-1")
        assert deleted_baselines == 1
        assert deleted_snapshots == 1
        assert kpi_service.get_all_baselines("pilot-1") == []
        assert kpi_service.get_snapshots("energy_per_unit", "pilot-1") == []
