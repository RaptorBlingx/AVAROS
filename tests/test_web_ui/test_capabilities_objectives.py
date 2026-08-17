"""Tests for dynamic capabilities and explicit KPI objectives."""

from __future__ import annotations

from fastapi.testclient import TestClient

from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


def _activate_profile(settings_service: SettingsService) -> None:
    settings_service.create_profile(
        "quality-site",
        PlatformConfig(
            platform_type="custom_rest",
            api_url="https://api.example.test",
        ),
    )
    settings_service.set_active_profile("quality-site")


def test_capability_manifest_reflects_active_mapping_and_read_only_mode(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    _activate_profile(settings_service)
    settings_service.set_metric_mapping(
        "oee",
        {
            "endpoint": "/values",
            "json_path": "$.records[0].value",
            "unit": "%",
        },
    )

    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "quality-site"
    assert body["read_only"] is True
    assert "machine_control" in body["unsupported"]
    assert "anomaly" not in body["operations"]
    assert {row["id"] for row in body["metrics"]} == {"oee"}


def test_objective_crud_is_profile_scoped(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    _activate_profile(settings_service)
    payload = {
        "metric": "oee",
        "asset_id": "Line-1",
        "mode": "threshold",
        "comparator": "at_least",
        "target_value": 85.0,
        "unit": "%",
    }

    saved = client.put("/api/v1/config/objectives/oee/Line-1", json=payload)
    assert saved.status_code == 200
    assert settings_service.get_kpi_objective("oee", "Line-1")["target_value"] == 85.0

    listed = client.get("/api/v1/config/objectives")
    assert listed.status_code == 200
    assert listed.json() == [payload | {"baseline_value": None, "improvement_percent": None}]

    deleted = client.delete("/api/v1/config/objectives/oee/Line-1")
    assert deleted.status_code == 204
    assert settings_service.get_kpi_objective("oee", "Line-1") is None


def test_objective_rejects_incomplete_threshold(client: TestClient) -> None:
    payload = {
        "metric": "oee",
        "asset_id": "Line-1",
        "mode": "threshold",
        "comparator": "at_least",
    }

    response = client.put("/api/v1/config/objectives/oee/Line-1", json=payload)

    assert response.status_code == 422
