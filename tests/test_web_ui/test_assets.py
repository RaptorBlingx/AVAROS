"""Tests for platform-agnostic asset router endpoints."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from main import app
from dependencies import get_adapter_factory
from skill.domain.models import Asset
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


@pytest.fixture()
def reneryo_profile(settings_service: SettingsService) -> None:
    """Ensure a writable Reneryo profile is active for mapping tests."""
    if settings_service.get_profile("reneryo") is None:
        settings_service.create_profile(
            "reneryo",
            PlatformConfig(platform_type="reneryo", api_url="https://reneryo.example.com"),
        )
    settings_service.set_active_profile("reneryo")


def test_discover_assets_returns_empty_on_unconfigured(
    client: TestClient,
) -> None:
    """Unconfigured profile discovery should return empty asset list."""
    response = client.get("/api/v1/assets/discover")

    assert response.status_code == 200
    body = response.json()
    assert body["platform_type"] == "unconfigured"
    assert body["supports_discovery"] is False
    assert isinstance(body["assets"], list)
    assert len(body["assets"]) == 0


def test_discover_assets_uses_adapter_factory_dependency(
    client: TestClient,
) -> None:
    """Discover endpoint should source assets through AdapterFactory adapter."""
    adapter = Mock()
    adapter.initialize = AsyncMock(return_value=None)
    adapter.shutdown = AsyncMock(return_value=None)
    adapter.supports_asset_discovery.return_value = True
    adapter.list_assets = AsyncMock(
        return_value=[
            Asset(
                asset_id="line-a",
                display_name="Line A",
                asset_type="line",
                aliases=["line alpha"],
            ),
        ],
    )
    factory = Mock()
    factory.create.return_value = adapter

    app.dependency_overrides[get_adapter_factory] = lambda: factory
    try:
        response = client.get("/api/v1/assets/discover")
    finally:
        app.dependency_overrides.pop(get_adapter_factory, None)

    assert response.status_code == 200
    adapter.list_assets.assert_awaited_once()
    body = response.json()
    assert body["assets"] == [
        {
            "asset_id": "line-a",
            "display_name": "Line A",
            "asset_type": "line",
            "aliases": ["line alpha"],
            "metadata": {},
        },
    ]


def test_discover_assets_skips_live_discovery_when_adapter_disables_it(
    client: TestClient,
) -> None:
    """Adapters without live discovery support should return empty assets."""
    adapter = Mock()
    adapter.initialize = AsyncMock(return_value=None)
    adapter.shutdown = AsyncMock(return_value=None)
    adapter.list_assets = AsyncMock(return_value=[])
    adapter.supports_asset_discovery.return_value = False
    factory = Mock()
    factory.create.return_value = adapter

    app.dependency_overrides[get_adapter_factory] = lambda: factory
    try:
        response = client.get("/api/v1/assets/discover")
    finally:
        app.dependency_overrides.pop(get_adapter_factory, None)

    assert response.status_code == 200
    body = response.json()
    assert body["supports_discovery"] is False
    assert body["assets"] == []
    adapter.initialize.assert_not_awaited()
    adapter.list_assets.assert_not_awaited()
    adapter.shutdown.assert_not_awaited()


def test_config_assets_roundtrip_for_custom_rest_profile(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """Saved asset mappings should be retrievable via /api/v1/config/assets."""
    if settings_service.get_profile("custom") is None:
        settings_service.create_profile(
            "custom",
            PlatformConfig(platform_type="custom_rest", api_url="https://api.example.com"),
        )
    settings_service.set_active_profile("custom")

    payload = {
        "asset_mappings": {
            "line-1": {
                "display_name": "Line 1",
                "asset_type": "line",
                "aliases": ["line one"],
                "endpoint_template": "/api/energy/{asset_id}",
            },
        },
    }

    save_response = client.post("/api/v1/config/assets", json=payload)
    assert save_response.status_code == 200

    get_response = client.get("/api/v1/config/assets")
    assert get_response.status_code == 200
    assert get_response.json() == payload


def test_config_assets_rejects_empty_asset_mapping(
    client: TestClient,
    settings_service: SettingsService,
) -> None:
    """Saving empty per-asset mappings should return HTTP 400."""
    if settings_service.get_profile("custom") is None:
        settings_service.create_profile(
            "custom",
            PlatformConfig(platform_type="custom_rest", api_url="https://api.example.com"),
        )
    settings_service.set_active_profile("custom")

    response = client.post(
        "/api/v1/config/assets",
        json={"asset_mappings": {"line-1": {}}},
    )
    assert response.status_code == 400
    assert "empty mapping" in response.json()["detail"].lower()


def test_assets_router_has_no_reneryo_imports() -> None:
    """DEC-001: assets router must not import from skill.adapters.reneryo."""
    router_file = (
        Path(__file__).resolve().parents[2] / "web-ui" / "routers" / "assets.py"
    )
    tree = ast.parse(router_file.read_text())

    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("skill.adapters.reneryo"):
                bad_imports.append(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("skill.adapters.reneryo"):
                    bad_imports.append(alias.name)

    assert bad_imports == []


# ── Generator mapping import tests ──────────────────────


def test_import_generator_mapping_transforms_and_persists(
    client: TestClient,
    settings_service: SettingsService,
    reneryo_profile: None,
) -> None:
    """Import generator mapping → merges metric_resources into asset mappings."""

    generator_output = {
        "mapping": {
            "energy_per_unit": {"line-1": "uuid-e1", "line-2": "uuid-e2"},
            "scrap_rate": {"line-1": "uuid-s1"},
        },
    }

    response = client.post("/api/v1/assets/import-generator-mapping", json=generator_output)

    assert response.status_code == 200
    body = response.json()
    assert body["imported_metrics"] == 2
    assert body["imported_resources"] == 3
    assert body["asset_mappings"]["line-1"]["metric_resources"]["energy_per_unit"] == "uuid-e1"
    assert body["asset_mappings"]["line-1"]["metric_resources"]["scrap_rate"] == "uuid-s1"
    assert body["asset_mappings"]["line-2"]["metric_resources"]["energy_per_unit"] == "uuid-e2"


def test_import_generator_mapping_merges_with_existing(
    client: TestClient,
    settings_service: SettingsService,
    reneryo_profile: None,
) -> None:
    """Existing asset fields (display_name, etc.) are preserved after import."""

    settings_service.set_asset_mappings({
        "line-1": {
            "display_name": "Line 1",
            "asset_type": "line",
            "aliases": ["line one"],
            "metric_resources": {"oee": "uuid-oee-old"},
        },
    })

    generator_output = {
        "mapping": {
            "energy_per_unit": {"line-1": "uuid-epu"},
        },
    }

    response = client.post("/api/v1/assets/import-generator-mapping", json=generator_output)
    assert response.status_code == 200
    body = response.json()

    line1 = body["asset_mappings"]["line-1"]
    assert line1["display_name"] == "Line 1"
    assert line1["aliases"] == ["line one"]
    assert line1["metric_resources"]["oee"] == "uuid-oee-old"
    assert line1["metric_resources"]["energy_per_unit"] == "uuid-epu"


def test_import_generator_mapping_rejects_empty(
    client: TestClient,
    settings_service: SettingsService,
    reneryo_profile: None,
) -> None:
    """Empty mapping payload should return 400."""

    response = client.post(
        "/api/v1/assets/import-generator-mapping",
        json={"mapping": {}},
    )
    assert response.status_code == 400


def test_import_generator_mapping_on_mock_profile_fails(
    client: TestClient,
) -> None:
    """Mock profile should reject mapping import (read-only)."""
    response = client.post(
        "/api/v1/assets/import-generator-mapping",
        json={"mapping": {"energy_per_unit": {"line-1": "uuid-1"}}},
    )
    assert response.status_code == 400


def test_import_generator_mapping_rejects_unknown_metric_names(
    client: TestClient,
    settings_service: SettingsService,
    reneryo_profile: None,
) -> None:
    """Unknown metric names should fail fast with HTTP 422."""
    settings_service.set_asset_mappings({
        "line-1": {"display_name": "Line 1"},
    })

    response = client.post(
        "/api/v1/assets/import-generator-mapping",
        json={"mapping": {"fake_metric": {"line-1": "uuid-x"}}},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Unknown metric names: fake_metric" in detail
    assert "Valid metrics:" in detail
    assert settings_service.get_asset_mappings() == {"line-1": {"display_name": "Line 1"}}


def test_config_assets_preserves_existing_metric_resources_when_missing_in_payload(
    client: TestClient,
    settings_service: SettingsService,
    reneryo_profile: None,
) -> None:
    """Saving UI rows without metric_resources must not wipe imported mappings."""
    settings_service.set_asset_mappings({
        "Line-1": {
            "display_name": "Line-1",
            "asset_type": "seu",
            "aliases": [],
            "seu_id": "old-seu",
            "metric_resources": {
                "oee": "uuid-oee-1",
                "energy_total": "uuid-energy-1",
            },
        },
    })

    response = client.post(
        "/api/v1/config/assets",
        json={
            "asset_mappings": {
                "Line-1": {
                    "display_name": "Line-1",
                    "asset_type": "seu",
                    "aliases": [],
                    "seu_id": "new-seu",
                },
            },
        },
    )
    assert response.status_code == 200
    line1 = response.json()["asset_mappings"]["Line-1"]
    assert line1["seu_id"] == "new-seu"
    assert line1["metric_resources"]["oee"] == "uuid-oee-1"
    assert line1["metric_resources"]["energy_total"] == "uuid-energy-1"
