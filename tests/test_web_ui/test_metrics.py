"""
Tests for metric mapping CRUD endpoints.

Covers:
    - POST   /api/v1/config/metrics            — create mapping
    - GET    /api/v1/config/metrics            — list all mappings
    - PUT    /api/v1/config/metrics/{name}     — update mapping
    - DELETE /api/v1/config/metrics/{name}     — delete mapping
    - Canonical metric name validation
    - Duplicate / missing metric handling
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from skill.services.settings import (
    PlatformConfig,
    SettingsService,
)


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture()
def energy_mapping_payload() -> dict[str, Any]:
    """Valid energy_per_unit metric mapping."""
    return {
        "canonical_metric": "energy_per_unit",
        "endpoint": "/api/v1/kpis/energy",
        "json_path": "$.data.value",
        "unit": "kWh/unit",
        "transform": None,
    }


@pytest.fixture()
def scrap_mapping_payload() -> dict[str, Any]:
    """Valid scrap_rate metric mapping."""
    return {
        "canonical_metric": "scrap_rate",
        "endpoint": "/api/v1/kpis/scrap",
        "json_path": "$.data.rate",
        "unit": "%",
        "transform": None,
    }


@pytest.fixture(autouse=True)
def active_profile(settings_service: SettingsService) -> None:
    """Use a non-mock active profile for legacy API compatibility tests."""
    if settings_service.get_profile("reneryo") is None:
        settings_service.create_profile(
            "reneryo",
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.example.com",
            ),
        )
    settings_service.set_active_profile("reneryo")


# ══════════════════════════════════════════════════════════
# POST /api/v1/config/metrics
# ══════════════════════════════════════════════════════════


class TestCreateMetricMapping:
    """Tests for creating a metric mapping."""

    def test_create_mapping_returns_201(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
    ) -> None:
        """POST with valid payload returns 201."""
        response = client.post(
            "/api/v1/config/metrics",
            json=energy_mapping_payload,
        )

        assert response.status_code == 201

    def test_create_mapping_returns_saved_data(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
    ) -> None:
        """Response body matches the submitted mapping."""
        response = client.post(
            "/api/v1/config/metrics",
            json=energy_mapping_payload,
        )

        body = response.json()
        assert body["canonical_metric"] == "energy_per_unit"
        assert body["endpoint"] == "/api/v1/kpis/energy"
        assert body["json_path"] == "$.data.value"
        assert body["unit"] == "kWh/unit"

    def test_create_mapping_with_transform(
        self,
        client: TestClient,
    ) -> None:
        """Optional transform field is stored correctly."""
        payload = {
            "canonical_metric": "co2_per_unit",
            "endpoint": "/api/v1/kpis/co2",
            "json_path": "$.emissions.value",
            "unit": "kgCO2/unit",
            "transform": "multiply_by_1000",
        }

        body = client.post("/api/v1/config/metrics", json=payload).json()

        assert body["transform"] == "multiply_by_1000"

    def test_create_mapping_transform_null_by_default(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
    ) -> None:
        """transform defaults to null when not provided."""
        body = client.post(
            "/api/v1/config/metrics",
            json=energy_mapping_payload,
        ).json()

        assert body["transform"] is None


class TestCreateMetricMappingValidation:
    """Validation error tests for metric mapping creation."""

    def test_reject_invalid_canonical_metric(
        self,
        client: TestClient,
    ) -> None:
        """Invalid canonical_metric name returns 422."""
        payload = {
            "canonical_metric": "totally_invalid_metric",
            "endpoint": "/api/v1/kpis/nope",
            "json_path": "$.nope",
            "unit": "nope",
        }

        response = client.post("/api/v1/config/metrics", json=payload)

        assert response.status_code == 422

    def test_reject_empty_endpoint(
        self,
        client: TestClient,
    ) -> None:
        """Empty endpoint string returns 422."""
        payload = {
            "canonical_metric": "energy_per_unit",
            "endpoint": "",
            "json_path": "$.data.value",
            "unit": "kWh/unit",
        }

        response = client.post("/api/v1/config/metrics", json=payload)

        assert response.status_code == 422

    def test_reject_empty_json_path(
        self,
        client: TestClient,
    ) -> None:
        """Empty json_path string returns 422."""
        payload = {
            "canonical_metric": "energy_per_unit",
            "endpoint": "/api/v1/kpis/energy",
            "json_path": "",
            "unit": "kWh/unit",
        }

        response = client.post("/api/v1/config/metrics", json=payload)

        assert response.status_code == 422

    def test_reject_empty_unit(
        self,
        client: TestClient,
    ) -> None:
        """Empty unit string returns 422."""
        payload = {
            "canonical_metric": "energy_per_unit",
            "endpoint": "/api/v1/kpis/energy",
            "json_path": "$.data.value",
            "unit": "",
        }

        response = client.post("/api/v1/config/metrics", json=payload)

        assert response.status_code == 422

    def test_reject_missing_required_fields(
        self,
        client: TestClient,
    ) -> None:
        """Missing required fields returns 422."""
        response = client.post(
            "/api/v1/config/metrics",
            json={"canonical_metric": "energy_per_unit"},
        )

        assert response.status_code == 422


# ══════════════════════════════════════════════════════════
# GET /api/v1/config/metrics
# ══════════════════════════════════════════════════════════


class TestListMetricMappings:
    """Tests for listing all metric mappings."""

    def test_list_empty_returns_empty_array(
        self,
        client: TestClient,
    ) -> None:
        """Fresh DB returns an empty array."""
        response = client.get("/api/v1/config/metrics")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_mappings(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
        scrap_mapping_payload: dict[str, Any],
    ) -> None:
        """All created mappings appear in the list."""
        client.post("/api/v1/config/metrics", json=energy_mapping_payload)
        client.post("/api/v1/config/metrics", json=scrap_mapping_payload)

        response = client.get("/api/v1/config/metrics")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        names = {m["canonical_metric"] for m in items}
        assert names == {"energy_per_unit", "scrap_rate"}

    def test_list_response_has_correct_structure(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
    ) -> None:
        """Each item in the list has all expected fields."""
        client.post("/api/v1/config/metrics", json=energy_mapping_payload)

        items = client.get("/api/v1/config/metrics").json()

        expected_keys = {
            "canonical_metric",
            "endpoint",
            "json_path",
            "unit",
            "transform",
        }
        assert set(items[0].keys()) == expected_keys


# ══════════════════════════════════════════════════════════
# PUT /api/v1/config/metrics/{metric_name}
# ══════════════════════════════════════════════════════════


class TestUpdateMetricMapping:
    """Tests for updating an existing metric mapping."""

    def test_update_existing_mapping(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
    ) -> None:
        """PUT on existing mapping updates it and returns 200."""
        client.post("/api/v1/config/metrics", json=energy_mapping_payload)

        updated = {
            **energy_mapping_payload,
            "endpoint": "/api/v2/kpis/energy-new",
        }
        response = client.put(
            "/api/v1/config/metrics/energy_per_unit",
            json=updated,
        )

        assert response.status_code == 200
        assert response.json()["endpoint"] == "/api/v2/kpis/energy-new"

    def test_update_nonexistent_mapping_returns_404(
        self,
        client: TestClient,
    ) -> None:
        """PUT on missing mapping returns 404."""
        payload = {
            "canonical_metric": "energy_per_unit",
            "endpoint": "/api/v1/kpis/energy",
            "json_path": "$.data.value",
            "unit": "kWh/unit",
        }

        response = client.put(
            "/api/v1/config/metrics/energy_per_unit",
            json=payload,
        )

        assert response.status_code == 404

    def test_update_body_metric_must_match_path(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
    ) -> None:
        """Body canonical_metric must equal path parameter."""
        client.post("/api/v1/config/metrics", json=energy_mapping_payload)

        mismatched = {
            **energy_mapping_payload,
            "canonical_metric": "scrap_rate",
        }
        response = client.put(
            "/api/v1/config/metrics/energy_per_unit",
            json=mismatched,
        )

        assert response.status_code == 422
        assert "must match" in response.json()["detail"].lower()

    def test_update_invalid_metric_name_returns_422(
        self,
        client: TestClient,
    ) -> None:
        """PUT with invalid metric name in path returns 422."""
        payload = {
            "canonical_metric": "fake_metric",
            "endpoint": "/api",
            "json_path": "$.x",
            "unit": "u",
        }

        response = client.put(
            "/api/v1/config/metrics/fake_metric",
            json=payload,
        )

        assert response.status_code == 422


# ══════════════════════════════════════════════════════════
# DELETE /api/v1/config/metrics/{metric_name}
# ══════════════════════════════════════════════════════════


class TestDeleteMetricMapping:
    """Tests for deleting a metric mapping."""

    def test_delete_existing_returns_204(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
    ) -> None:
        """DELETE on existing mapping returns 204 No Content."""
        client.post("/api/v1/config/metrics", json=energy_mapping_payload)

        response = client.delete("/api/v1/config/metrics/energy_per_unit")

        assert response.status_code == 204

    def test_delete_nonexistent_returns_404(
        self,
        client: TestClient,
    ) -> None:
        """DELETE on missing mapping returns 404."""
        response = client.delete("/api/v1/config/metrics/energy_per_unit")

        assert response.status_code == 404

    def test_delete_invalid_metric_name_returns_422(
        self,
        client: TestClient,
    ) -> None:
        """DELETE with invalid canonical metric name returns 422."""
        response = client.delete("/api/v1/config/metrics/not_a_real_metric")

        assert response.status_code == 422

    def test_delete_removes_from_list(
        self,
        client: TestClient,
        energy_mapping_payload: dict[str, Any],
        scrap_mapping_payload: dict[str, Any],
    ) -> None:
        """After deletion, mapping no longer appears in list."""
        client.post("/api/v1/config/metrics", json=energy_mapping_payload)
        client.post("/api/v1/config/metrics", json=scrap_mapping_payload)
        client.delete("/api/v1/config/metrics/energy_per_unit")

        items = client.get("/api/v1/config/metrics").json()

        assert len(items) == 1
        assert items[0]["canonical_metric"] == "scrap_rate"
