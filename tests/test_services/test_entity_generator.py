"""Tests for dynamic asset entity file generation."""

from __future__ import annotations

from pathlib import Path

from skill.domain.models import Asset
from skill.services.entity_generator import (
    regenerate_asset_entities,
    regenerate_asset_entities_for_all_locales,
)
from skill.services.settings import PlatformConfig, SettingsService


def _read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_regenerate_asset_entities_writes_display_names_and_aliases(tmp_path: Path) -> None:
    """Entity file should include display names and aliases."""
    locale_dir = tmp_path / "en-us"
    assets = [
        Asset(
            asset_id="line-1",
            display_name="Line 1",
            asset_type="line",
            aliases=["Production Line 1", "line 1"],
        )
    ]

    regenerate_asset_entities(assets, locale_dir)

    lines = _read_lines(locale_dir / "asset.entity")
    assert "line 1" in lines
    assert "production line 1" in lines
    assert _read_lines(locale_dir / "asset_a.entity") == lines
    assert _read_lines(locale_dir / "asset_b.entity") == lines


def test_regenerate_asset_entities_deduplicates_entries(tmp_path: Path) -> None:
    """Duplicate display names/aliases should appear once."""
    locale_dir = tmp_path / "en-us"
    assets = [
        Asset(
            asset_id="line-1",
            display_name="Line 1",
            asset_type="line",
            aliases=["line 1", " Line   1 "],
        ),
        Asset(
            asset_id="line-2",
            display_name="line 1",
            asset_type="line",
            aliases=[],
        ),
    ]

    regenerate_asset_entities(assets, locale_dir)

    lines = _read_lines(locale_dir / "asset.entity")
    assert lines.count("line 1") == 1


def test_regenerate_asset_entities_empty_assets_falls_back_to_mock_defaults(
    tmp_path: Path,
) -> None:
    """Empty asset input should still produce non-empty placeholder files."""
    locale_dir = tmp_path / "en-us"

    regenerate_asset_entities([], locale_dir)

    lines = _read_lines(locale_dir / "asset.entity")
    assert lines
    assert "line-1" in lines
    assert "line 1" in lines


def test_regenerate_asset_entities_for_all_locales(tmp_path: Path) -> None:
    """Generator should write files for every locale directory under root."""
    locale_root = tmp_path / "locale"
    (locale_root / "en-us").mkdir(parents=True)
    (locale_root / "tr-tr").mkdir(parents=True)
    assets = [
        Asset(
            asset_id="machine-a",
            display_name="Machine A",
            asset_type="machine",
            aliases=["machine a"],
        )
    ]

    regenerate_asset_entities_for_all_locales(assets, locale_root)

    for locale in ("en-us", "tr-tr"):
        lines = _read_lines(locale_root / locale / "asset.entity")
        assert "machine a" in lines
        assert _read_lines(locale_root / locale / "asset_a.entity") == lines
        assert _read_lines(locale_root / locale / "asset_b.entity") == lines


def test_set_asset_mappings_triggers_entity_regeneration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Saving mappings via SettingsService should regenerate locale entities."""
    locale_root = tmp_path / "locale"
    (locale_root / "en-us").mkdir(parents=True)
    (locale_root / "de-de").mkdir(parents=True)
    monkeypatch.setenv("AVAROS_LOCALE_ROOT", str(locale_root))

    service = SettingsService()
    service.initialize()
    service.create_profile(
        "reneryo",
        PlatformConfig(platform_type="reneryo", api_url="https://api.example.com"),
    )
    service.set_active_profile("reneryo")

    service.set_asset_mappings(
        {
            "Line-1": {
                "display_name": "Line 1",
                "asset_type": "line",
                "aliases": ["production line 1"],
                "seu_id": "seu-1",
            }
        }
    )

    for locale in ("en-us", "de-de"):
        lines = _read_lines(locale_root / locale / "asset.entity")
        assert "line 1" in lines
        assert "production line 1" in lines

