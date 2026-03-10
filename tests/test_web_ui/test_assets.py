"""Tests for platform-agnostic asset router endpoints."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from main import app
from dependencies import get_adapter_factory
from skill.domain.models import Asset
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


def test_discover_assets_returns_generic_schema_on_mock(
    client: TestClient,
) -> None:
    """Mock profile discovery should return unified asset list schema."""
    response = client.get("/api/v1/assets/discover")

    assert response.status_code == 200
    body = response.json()
    assert body["platform_type"] == "mock"
    assert isinstance(body["supports_discovery"], bool)
    assert isinstance(body["assets"], list)
    assert len(body["assets"]) > 0
    assert set(body["assets"][0].keys()) >= {
        "asset_id",
        "display_name",
        "asset_type",
        "aliases",
    }


def test_discover_assets_uses_adapter_factory_dependency(
    client: TestClient,
) -> None:
    """Discover endpoint should source assets through AdapterFactory adapter."""
    adapter = Mock()
    adapter.initialize = AsyncMock(return_value=None)
    adapter.shutdown = AsyncMock(return_value=None)
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
