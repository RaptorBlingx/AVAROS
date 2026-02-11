"""
Production Data Router Test Suite

Covers all 6 REST endpoints:
    - POST /api/v1/production-data → 201
    - POST /api/v1/production-data/bulk → CSV upload
    - GET /api/v1/production-data → list with filters
    - GET /api/v1/production-data/summary → aggregation
    - DELETE /api/v1/production-data/{id} → 200/404
    - GET /api/v1/production-data/template → CSV file
"""

from __future__ import annotations

import sys
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
    get_production_data_service,
    get_settings_service,
)
from skill.services.database import Base  # noqa: E402
from skill.services.production_data import ProductionDataService  # noqa: E402
from skill.services.settings import SettingsService  # noqa: E402


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def production_service() -> ProductionDataService:
    """In-memory ProductionDataService with thread-safe StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    svc = ProductionDataService(database_url="sqlite:///:memory:")
    svc._engine = engine
    svc._session_factory = sessionmaker(
        bind=engine, expire_on_commit=False,
    )
    Base.metadata.create_all(engine)
    svc._initialized = True
    return svc


@pytest.fixture
def client(
    production_service: ProductionDataService,
) -> Generator[TestClient, None, None]:
    """Test client with both settings + production overrides and auth."""
    test_settings = SettingsService()
    test_settings.initialize()

    app.dependency_overrides[get_settings_service] = lambda: test_settings
    app.dependency_overrides[get_production_data_service] = (
        lambda: production_service
    )

    with TestClient(app, headers={"X-API-Key": WEB_API_KEY}) as tc:
        yield tc

    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════
# POST — Single Record
# ══════════════════════════════════════════════════════════


class TestPostSingleRecord:
    """POST /api/v1/production-data."""

    def test_create_record_201(self, client: TestClient) -> None:
        """Valid payload returns 201 with record ID."""
        payload = {
            "record_date": "2026-01-15",
            "asset_id": "Line-1",
            "production_count": 500,
            "good_count": 485,
            "material_consumed_kg": 120.5,
            "shift": "morning",
        }
        resp = client.post("/api/v1/production-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] > 0
        assert data["asset_id"] == "Line-1"
        assert data["production_count"] == 500

    def test_create_record_validation_negative(
        self, client: TestClient,
    ) -> None:
        """Negative production_count → 422."""
        payload = {
            "record_date": "2026-01-15",
            "asset_id": "Line-1",
            "production_count": -1,
            "good_count": 0,
            "material_consumed_kg": 0,
        }
        resp = client.post("/api/v1/production-data", json=payload)
        assert resp.status_code == 422

    def test_create_record_missing_asset(self, client: TestClient) -> None:
        """Missing asset_id → 422."""
        payload = {
            "record_date": "2026-01-15",
            "production_count": 100,
            "good_count": 95,
            "material_consumed_kg": 50.0,
        }
        resp = client.post("/api/v1/production-data", json=payload)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# POST — CSV Upload
# ══════════════════════════════════════════════════════════


class TestPostCsvUpload:
    """POST /api/v1/production-data/bulk."""

    def test_upload_valid_csv(self, client: TestClient) -> None:
        """Valid CSV returns success with counts."""
        csv_content = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,500,485,120.5\n"
            "2026-01-16,Line-1,480,470,115.0\n"
        )
        resp = client.post(
            "/api/v1/production-data/bulk",
            files={"file": ("data.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 2
        assert data["valid_rows"] == 2
        assert data["inserted"] == 2
        assert data["errors"] == []

    def test_upload_csv_with_errors(self, client: TestClient) -> None:
        """CSV with invalid rows reports errors and inserts valid rows."""
        csv_content = (
            "date,asset_id,production_count,good_count,"
            "material_consumed_kg\n"
            "2026-01-15,Line-1,500,485,120.5\n"
            "BAD-DATE,Line-2,100,95,50.0\n"
        )
        resp = client.post(
            "/api/v1/production-data/bulk",
            files={"file": ("data.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid_rows"] == 1
        assert data["inserted"] == 1
        assert len(data["errors"]) == 1


# ══════════════════════════════════════════════════════════
# GET — List Records
# ══════════════════════════════════════════════════════════


class TestGetListRecords:
    """GET /api/v1/production-data."""

    def test_list_empty(self, client: TestClient) -> None:
        """No records → empty list."""
        resp = client.get("/api/v1/production-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["records"] == []
        assert data["total"] == 0

    def test_list_with_records(self, client: TestClient) -> None:
        """Created records appear in list."""
        # Insert a record first
        client.post("/api/v1/production-data", json={
            "record_date": "2026-01-15",
            "asset_id": "Line-1",
            "production_count": 100,
            "good_count": 95,
            "material_consumed_kg": 50.0,
        })
        resp = client.get("/api/v1/production-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["asset_id"] == "Line-1"

    def test_list_filter_by_asset(self, client: TestClient) -> None:
        """Filter by asset_id query param."""
        client.post("/api/v1/production-data", json={
            "record_date": "2026-01-15",
            "asset_id": "Line-1",
            "production_count": 100,
            "good_count": 95,
            "material_consumed_kg": 50.0,
        })
        client.post("/api/v1/production-data", json={
            "record_date": "2026-01-15",
            "asset_id": "Line-2",
            "production_count": 200,
            "good_count": 190,
            "material_consumed_kg": 80.0,
        })
        resp = client.get(
            "/api/v1/production-data",
            params={"asset_id": "Line-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["asset_id"] == "Line-1"


# ══════════════════════════════════════════════════════════
# GET — Summary
# ══════════════════════════════════════════════════════════


class TestGetSummary:
    """GET /api/v1/production-data/summary."""

    def test_summary_with_data(self, client: TestClient) -> None:
        """Summary returns correct aggregation."""
        client.post("/api/v1/production-data", json={
            "record_date": "2026-01-15",
            "asset_id": "Line-1",
            "production_count": 500,
            "good_count": 485,
            "material_consumed_kg": 120.5,
        })
        resp = client.get(
            "/api/v1/production-data/summary",
            params={
                "asset_id": "Line-1",
                "start_date": "2026-01-15",
                "end_date": "2026-01-15",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_produced"] == 500
        assert data["total_good"] == 485
        assert data["record_count"] == 1
        assert data["material_efficiency_pct"] == 97.0

    def test_summary_missing_params(self, client: TestClient) -> None:
        """Missing required query params → 422."""
        resp = client.get("/api/v1/production-data/summary")
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# DELETE — Single Record
# ══════════════════════════════════════════════════════════


class TestDeleteRecord:
    """DELETE /api/v1/production-data/{id}."""

    def test_delete_existing(self, client: TestClient) -> None:
        """Delete existing record → 200 with status."""
        resp = client.post("/api/v1/production-data", json={
            "record_date": "2026-01-15",
            "asset_id": "Line-1",
            "production_count": 100,
            "good_count": 95,
            "material_consumed_kg": 50.0,
        })
        record_id = resp.json()["id"]
        resp = client.delete(f"/api/v1/production-data/{record_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_not_found(self, client: TestClient) -> None:
        """Delete non-existent record → 404."""
        resp = client.delete("/api/v1/production-data/9999")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# GET — CSV Template
# ══════════════════════════════════════════════════════════


class TestCsvTemplate:
    """GET /api/v1/production-data/template."""

    def test_template_download(self, client: TestClient) -> None:
        """Template returns CSV content."""
        resp = client.get("/api/v1/production-data/template")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        assert "date" in content
        assert "asset_id" in content
        assert "production_count" in content
        assert "Line-1" in content  # sample row
