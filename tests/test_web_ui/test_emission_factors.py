"""
Emission Factor API Endpoint Tests

Tests for the /api/v1/config/emission-factors endpoints.
Uses the shared Web UI conftest (TestClient + in-memory SettingsService).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ══════════════════════════════════════════════════════════
# Emission Factor CRUD Endpoints
# ══════════════════════════════════════════════════════════


class TestEmissionFactorEndpoints:
    """Tests for emission factor API endpoints."""

    def test_list_empty(self, client: TestClient) -> None:
        """Empty factor list on fresh database."""
        resp = client.get("/api/v1/config/emission-factors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["factors"] == []

    def test_create_factor(self, client: TestClient) -> None:
        """POST creates emission factor successfully."""
        payload = {
            "energy_source": "electricity",
            "factor": 0.48,
            "country": "TR",
            "source": "IEA 2024",
            "year": 2024,
        }
        resp = client.post(
            "/api/v1/config/emission-factors", json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["energy_source"] == "electricity"
        assert data["factor"] == 0.48
        assert data["country"] == "TR"

    def test_create_invalid_source(self, client: TestClient) -> None:
        """POST with invalid energy_source returns 422."""
        payload = {
            "energy_source": "nuclear",
            "factor": 0.01,
        }
        resp = client.post(
            "/api/v1/config/emission-factors", json=payload,
        )
        assert resp.status_code == 422

    def test_create_negative_factor(self, client: TestClient) -> None:
        """POST with factor <= 0 returns 422."""
        payload = {
            "energy_source": "electricity",
            "factor": -0.5,
        }
        resp = client.post(
            "/api/v1/config/emission-factors", json=payload,
        )
        assert resp.status_code == 422

    def test_create_zero_factor(self, client: TestClient) -> None:
        """POST with factor=0 returns 422."""
        payload = {
            "energy_source": "electricity",
            "factor": 0,
        }
        resp = client.post(
            "/api/v1/config/emission-factors", json=payload,
        )
        assert resp.status_code == 422

    def test_list_after_create(self, client: TestClient) -> None:
        """GET returns factors after creation."""
        client.post(
            "/api/v1/config/emission-factors",
            json={"energy_source": "electricity", "factor": 0.48},
        )
        resp = client.get("/api/v1/config/emission-factors")
        assert resp.status_code == 200
        factors = resp.json()["factors"]
        assert len(factors) == 1
        assert factors[0]["energy_source"] == "electricity"

    def test_delete_factor(self, client: TestClient) -> None:
        """DELETE removes the factor."""
        client.post(
            "/api/v1/config/emission-factors",
            json={"energy_source": "gas", "factor": 0.20},
        )
        resp = client.delete(
            "/api/v1/config/emission-factors/gas",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify it's gone
        resp = client.get("/api/v1/config/emission-factors")
        assert len(resp.json()["factors"]) == 0

    def test_delete_nonexistent(self, client: TestClient) -> None:
        """DELETE for missing factor returns 404."""
        resp = client.delete(
            "/api/v1/config/emission-factors/electricity",
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
# Presets Endpoint
# ══════════════════════════════════════════════════════════


class TestEmissionFactorPresets:
    """Tests for GET /emission-factors/presets."""

    def test_list_presets(self, client: TestClient) -> None:
        """GET /presets returns country defaults."""
        resp = client.get(
            "/api/v1/config/emission-factors/presets",
        )
        assert resp.status_code == 200
        presets = resp.json()
        assert len(presets) > 0

    def test_presets_include_turkey(self, client: TestClient) -> None:
        """Presets include Türkiye electricity factor."""
        resp = client.get(
            "/api/v1/config/emission-factors/presets",
        )
        presets = resp.json()
        turkey_elec = [
            p for p in presets
            if p["country"] == "TR"
            and p["energy_source"] == "electricity"
        ]
        assert len(turkey_elec) == 1
        assert turkey_elec[0]["factor"] == 0.48

    def test_presets_all_have_positive_factor(
        self, client: TestClient,
    ) -> None:
        """All preset factors are positive."""
        resp = client.get(
            "/api/v1/config/emission-factors/presets",
        )
        presets = resp.json()
        for preset in presets:
            assert preset["factor"] > 0, (
                f"{preset['country']}/{preset['energy_source']} "
                f"has factor={preset['factor']}"
            )
