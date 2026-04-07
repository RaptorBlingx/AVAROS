"""Tests for alert configuration API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from skill.services.settings import SettingsService


class TestAlertConfigEndpoints:
    """Validate alert config read/write including query threshold split."""

    def test_get_alert_config_includes_query_threshold(
        self,
        client: TestClient,
    ) -> None:
        """GET response includes both alert and conversational thresholds."""
        response = client.get("/api/v1/config/alert-config")

        assert response.status_code == 200
        body = response.json()
        assert "z_score_threshold" in body
        assert "query_z_score_threshold" in body

    def test_put_alert_config_persists_query_threshold(
        self,
        client: TestClient,
        settings_service: SettingsService,
    ) -> None:
        """PUT stores conversational threshold independently from alert threshold."""
        payload = {
            "enabled": True,
            "interval_seconds": 3600,
            "severity_threshold": "medium",
            "cooldown_minutes": 30,
            "monitored_pairs": [],
            "z_score_threshold": 3.4,
            "query_z_score_threshold": 1.9,
        }

        response = client.put("/api/v1/config/alert-config", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["z_score_threshold"] == 3.4
        assert body["query_z_score_threshold"] == 1.9
        assert settings_service.get_alert_config().z_score_threshold == 3.4
        assert settings_service.get_query_anomaly_threshold() == 1.9
