"""Tests for the Intent Activation API (``/api/v1/config/intents``).

Covers:
- GET  /api/v1/config/intents — list all intents
- PUT  /api/v1/config/intents/{name} — toggle activation state
- Default state (all active), metric dependency cross-check,
  unknown intent rejection
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skill.services.settings import (
    KNOWN_INTENTS,
    PlatformConfig,
    SettingsService,
)


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
# 1. GET /api/v1/config/intents
# ══════════════════════════════════════════════════════════


class TestListIntents:
    """GET /api/v1/config/intents."""

    def test_list_intents_returns_200(self, client: TestClient) -> None:
        """Endpoint returns 200 OK."""
        resp = client.get("/api/v1/config/intents")
        assert resp.status_code == 200

    def test_list_intents_returns_all_eight(self, client: TestClient) -> None:
        """Response contains all 8 known intents."""
        data = client.get("/api/v1/config/intents").json()
        assert data["total"] == 8
        assert len(data["intents"]) == 8

    def test_list_intents_default_all_active(self, client: TestClient) -> None:
        """All intents default to active on fresh database."""
        data = client.get("/api/v1/config/intents").json()
        assert data["active_count"] == 8
        for intent in data["intents"]:
            assert intent["active"] is True

    def test_list_intents_contains_required_metrics(
        self, client: TestClient
    ) -> None:
        """Each intent has a non-empty required_metrics list."""
        data = client.get("/api/v1/config/intents").json()
        for intent in data["intents"]:
            assert isinstance(intent["required_metrics"], list)
            assert len(intent["required_metrics"]) > 0

    def test_list_intents_metrics_mapped_false_by_default(
        self, client: TestClient
    ) -> None:
        """metrics_mapped is False when no mappings exist."""
        data = client.get("/api/v1/config/intents").json()
        for intent in data["intents"]:
            assert intent["metrics_mapped"] is False

    def test_list_intents_metrics_mapped_true_after_mapping(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """metrics_mapped becomes True when required metrics are mapped."""
        # Map energy_per_unit — satisfies kpi.energy.per_unit
        settings_service.set_metric_mapping(
            "energy_per_unit",
            {"endpoint": "/api/energy", "json_path": "$.v", "unit": "kWh"},
        )
        data = client.get("/api/v1/config/intents").json()
        by_name = {i["intent_name"]: i for i in data["intents"]}
        assert by_name["kpi.energy.per_unit"]["metrics_mapped"] is True
        # oee is NOT mapped
        assert by_name["kpi.oee"]["metrics_mapped"] is False

    def test_list_intents_reflects_deactivation(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Deactivating an intent is reflected in the list."""
        settings_service.set_intent_active("kpi.oee", False)
        data = client.get("/api/v1/config/intents").json()
        assert data["active_count"] == 7
        by_name = {i["intent_name"]: i for i in data["intents"]}
        assert by_name["kpi.oee"]["active"] is False

    def test_list_intents_intent_names_match_known(
        self, client: TestClient
    ) -> None:
        """Returned intent names match KNOWN_INTENTS exactly."""
        data = client.get("/api/v1/config/intents").json()
        names = {i["intent_name"] for i in data["intents"]}
        assert names == set(KNOWN_INTENTS)


# ══════════════════════════════════════════════════════════
# 2. PUT /api/v1/config/intents/{intent_name}
# ══════════════════════════════════════════════════════════


class TestToggleIntent:
    """PUT /api/v1/config/intents/{intent_name}."""

    def test_deactivate_intent_returns_200(self, client: TestClient) -> None:
        """Deactivating a known intent returns 200."""
        resp = client.put(
            "/api/v1/config/intents/kpi.oee",
            json={"active": False},
        )
        assert resp.status_code == 200

    def test_deactivate_intent_returns_false(self, client: TestClient) -> None:
        """Response body shows active=False after deactivation."""
        data = client.put(
            "/api/v1/config/intents/kpi.oee",
            json={"active": False},
        ).json()
        assert data["intent_name"] == "kpi.oee"
        assert data["active"] is False

    def test_activate_intent_returns_true(self, client: TestClient) -> None:
        """Re-activating shows active=True."""
        client.put("/api/v1/config/intents/kpi.oee", json={"active": False})
        data = client.put(
            "/api/v1/config/intents/kpi.oee",
            json={"active": True},
        ).json()
        assert data["active"] is True

    def test_toggle_persists_across_requests(
        self, client: TestClient
    ) -> None:
        """Toggled state is visible in subsequent GET."""
        client.put("/api/v1/config/intents/kpi.oee", json={"active": False})
        data = client.get("/api/v1/config/intents").json()
        by_name = {i["intent_name"]: i for i in data["intents"]}
        assert by_name["kpi.oee"]["active"] is False

    def test_toggle_returns_required_metrics(
        self, client: TestClient
    ) -> None:
        """Toggle response includes required_metrics list."""
        data = client.put(
            "/api/v1/config/intents/kpi.oee",
            json={"active": True},
        ).json()
        assert data["required_metrics"] == ["oee"]

    def test_toggle_returns_metrics_mapped(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """Toggle response reflects correct metrics_mapped state."""
        settings_service.set_metric_mapping(
            "oee",
            {"endpoint": "/api/oee", "json_path": "$.v", "unit": "%"},
        )
        data = client.put(
            "/api/v1/config/intents/kpi.oee",
            json={"active": True},
        ).json()
        assert data["metrics_mapped"] is True

    def test_toggle_unknown_intent_returns_422(
        self, client: TestClient
    ) -> None:
        """Unknown intent name returns 422."""
        resp = client.put(
            "/api/v1/config/intents/bogus.intent",
            json={"active": True},
        )
        assert resp.status_code == 422

    def test_toggle_missing_body_returns_422(
        self, client: TestClient
    ) -> None:
        """Missing request body returns 422."""
        resp = client.put("/api/v1/config/intents/kpi.oee")
        assert resp.status_code == 422
