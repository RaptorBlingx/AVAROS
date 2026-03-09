"""Dynamic OVOS entity file generation for asset slots."""

from __future__ import annotations

from pathlib import Path

from skill.adapters.mock import MockAdapter
from skill.domain.models import Asset

_ENTITY_FILES = ("asset.entity", "asset_a.entity", "asset_b.entity")


def regenerate_asset_entities(assets: list[Asset], locale_dir: Path) -> None:
    """Generate OVOS asset entity files for one locale directory."""
    normalized_assets = assets if assets else _default_mock_assets()
    entries = _normalized_entries(normalized_assets)
    if not entries:
        entries = _normalized_entries(_default_mock_assets())
    content = "\n".join(entries) + "\n"

    locale_path = Path(locale_dir)
    locale_path.mkdir(parents=True, exist_ok=True)
    for filename in _ENTITY_FILES:
        (locale_path / filename).write_text(content, encoding="utf-8")


def regenerate_asset_entities_for_all_locales(
    assets: list[Asset],
    locale_root: Path,
) -> None:
    """Generate asset entity files for all locale subdirectories."""
    root = Path(locale_root)
    if not root.exists():
        return

    locale_dirs = sorted(path for path in root.iterdir() if path.is_dir())
    for locale_dir in locale_dirs:
        regenerate_asset_entities(assets, locale_dir)


def _normalized_entries(assets: list[Asset]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for asset in assets:
        for raw in [asset.display_name, *asset.aliases]:
            normalized = _normalize(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _normalize(value: str) -> str:
    return " ".join(str(value).strip().split()).lower()


def _default_mock_assets() -> list[Asset]:
    assets: list[Asset] = []
    for asset_name in MockAdapter._DEMO_ASSETS:
        assets.append(
            Asset(
                asset_id=asset_name,
                display_name=asset_name,
                asset_type=MockAdapter._infer_asset_type(asset_name),
                aliases=MockAdapter._build_asset_aliases(asset_name),
                metadata={"source": "mock_demo"},
            )
        )
    return assets
