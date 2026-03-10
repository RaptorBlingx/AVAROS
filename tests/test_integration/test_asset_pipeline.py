"""Integration tests for the end-to-end DEC-034 asset mapping pipeline."""

from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from skill._helpers import canonicalize_asset_id, get_asset_registry
from skill.adapters.factory import AdapterFactory
from skill.adapters.mock import MockAdapter
from skill.domain.exceptions import AssetNotFoundError
from skill.domain.models import Asset
from skill.services.entity_generator import (
    regenerate_asset_entities,
    regenerate_asset_entities_for_all_locales,
)
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService
from skill.use_cases.query_dispatcher import QueryDispatcher
from tests.conftest import build_test_settings_service


def _read_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _build_skill_harness(settings_service: SettingsService) -> Any:
    """Build minimal skill-like object that exercises canonicalization stack."""
    factory = AdapterFactory(settings_service=settings_service)
    adapter = factory.create()
    dispatcher = QueryDispatcher(adapter=adapter, settings_service=settings_service)
    log = SimpleNamespace(warning=lambda *_args, **_kwargs: None)

    class _Harness:
        def __init__(self):
            self.settings_service = settings_service
            self.dispatcher = dispatcher
            self.log = log
            self._asset_registry_cache = None
            self._asset_registry_profile = ""

        def _resolve_active_profile(self) -> str:
            return self.settings_service.get_active_profile_name()

        def _get_asset_registry(self, force_refresh: bool = False) -> list[Asset]:
            return get_asset_registry(self, force_refresh=force_refresh)

        def _canonicalize_asset_id(
            self,
            raw_asset: str,
            *,
            raise_on_unknown: bool = False,
        ) -> str:
            return canonicalize_asset_id(
                self,
                raw_asset,
                raise_on_unknown=raise_on_unknown,
            )

    return _Harness()


def test_asset_pipeline_end_to_end_resolves_voice_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Mock discovery -> Settings save -> entity files -> voice canonicalization."""
    # --- Arrange: locale dirs + SettingsService with a profile ---
    locale_root = tmp_path / "locale"
    (locale_root / "en-us").mkdir(parents=True)
    (locale_root / "tr-tr").mkdir(parents=True)
    monkeypatch.setenv("AVAROS_LOCALE_ROOT", str(locale_root))

    service = build_test_settings_service(
        database_url=f"sqlite:///{tmp_path / 'asset-pipeline.db'}",
    )
    service.create_profile(
        "reneryo-prod",
        PlatformConfig(platform_type="reneryo", api_url="https://reneryo.example.com"),
    )
    service.set_active_profile("reneryo-prod")

    # --- Act 1: Discovery + persist mappings ---
    adapter = MockAdapter()
    discovered_assets = asyncio.run(adapter.list_assets())
    assert len(discovered_assets) == 10

    mappings = {
        asset.asset_id: {
            "display_name": asset.display_name,
            "asset_type": asset.asset_type,
            "aliases": asset.aliases,
        }
        for asset in discovered_assets
    }
    # Add richer alias coverage for canonicalization assertions.
    mappings["Line-1"]["aliases"] = ["line 1", "production line one"]
    service.set_asset_mappings(mappings, profile="reneryo-prod")

    # --- Act 2: Entity file generation ---
    regenerate_asset_entities(discovered_assets, locale_root / "en-us")
    regenerate_asset_entities_for_all_locales(discovered_assets, locale_root)

    # --- Assert: entity files ---
    en_lines = _read_lines(locale_root / "en-us" / "asset.entity")
    tr_lines = _read_lines(locale_root / "tr-tr" / "asset.entity")
    assert "line 1" in en_lines
    assert "line 1" in tr_lines
    assert _read_lines(locale_root / "en-us" / "asset_a.entity") == en_lines
    assert _read_lines(locale_root / "en-us" / "asset_b.entity") == en_lines

    # --- Act 3: Voice canonicalization ---
    skill = _build_skill_harness(service)
    resolved = skill._canonicalize_asset_id("production line one", raise_on_unknown=True)
    assert resolved == "Line-1"

    # --- Assert: unknown asset raises with helpful message ---
    with pytest.raises(AssetNotFoundError) as exc_info:
        skill._canonicalize_asset_id("nonexistent thing", raise_on_unknown=True)
    exc = exc_info.value
    assert "Line-1" in exc.available_assets
    assert "Line-2" in exc.available_assets
    assert "Available assets are" in exc.user_message

    service.close()


def test_asset_profile_isolation_across_reneryo_custom_and_mock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Asset mappings must remain profile-scoped (DEC-029)."""
    locale_root = tmp_path / "locale"
    (locale_root / "en-us").mkdir(parents=True)
    monkeypatch.setenv("AVAROS_LOCALE_ROOT", str(locale_root))
    service = build_test_settings_service(
        database_url=f"sqlite:///{tmp_path / 'asset-isolation.db'}",
    )
    service.create_profile(
        "reneryo-prod",
        PlatformConfig(platform_type="reneryo", api_url="https://reneryo.example.com"),
    )
    service.create_profile(
        "generic-test",
        PlatformConfig(platform_type="custom_rest", api_url="https://rest.example.com"),
    )

    service.set_active_profile("reneryo-prod")
    service.set_asset_mappings(
        {
            "A": {"display_name": "Asset A", "asset_type": "line"},
            "B": {"display_name": "Asset B", "asset_type": "machine"},
            "C": {"display_name": "Asset C", "asset_type": "sensor"},
        }
    )

    service.set_active_profile("generic-test")
    service.set_asset_mappings(
        {
            "X": {"display_name": "Asset X", "asset_type": "machine"},
            "Y": {"display_name": "Asset Y", "asset_type": "line"},
        }
    )

    service.set_active_profile("reneryo-prod")
    assert set(service.get_asset_mappings().keys()) == {"A", "B", "C"}

    service.set_active_profile("generic-test")
    assert set(service.get_asset_mappings().keys()) == {"X", "Y"}

    service.set_active_profile("mock")
    assert service.get_asset_mappings() == {}
    service.close()


def test_web_ui_discover_endpoint_mock_profile_returns_generic_assets(tmp_path: Path) -> None:
    """Discover API should return platform-agnostic Asset schema on mock profile."""
    web_ui_dir = Path(__file__).resolve().parents[2] / "web-ui"
    if str(web_ui_dir) not in sys.path:
        sys.path.insert(0, str(web_ui_dir))

    from config import WEB_API_KEY  # type: ignore[import-not-found]
    from dependencies import get_settings_service  # type: ignore[import-not-found]
    from main import app  # type: ignore[import-not-found]

    settings = build_test_settings_service(
        database_url=f"sqlite:///{tmp_path / 'asset-web-ui.db'}",
    )
    settings.set_active_profile("mock")
    app.dependency_overrides[get_settings_service] = lambda: settings

    try:
        with TestClient(app, headers={"X-API-Key": WEB_API_KEY}) as client:
            response = client.get("/api/v1/assets/discover")
        assert response.status_code == 200
        body = response.json()
        assert body["platform_type"] == "mock"
        assert isinstance(body["assets"], list)
        assert len(body["assets"]) == 10
        first = body["assets"][0]
        assert set(first.keys()) >= {"asset_id", "display_name", "asset_type", "aliases"}
    finally:
        app.dependency_overrides.clear()
        settings.close()


def test_assets_router_has_no_reneryo_imports() -> None:
    """Discover request path must remain platform-agnostic (DEC-001)."""
    router_file = Path(__file__).resolve().parents[2] / "web-ui" / "routers" / "assets.py"
    tree = ast.parse(router_file.read_text(encoding="utf-8"))

    offending_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("skill.adapters.reneryo"):
                offending_modules.append(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("skill.adapters.reneryo"):
                    offending_modules.append(alias.name)

    assert offending_modules == []
