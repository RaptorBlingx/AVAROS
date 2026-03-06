"""Tests for asset canonicalization and list-assets voice handler."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from skill import AVAROSSkill
from skill.domain.exceptions import AssetNotFoundError
from skill.domain.models import Asset


def _message(**data):
    message = Mock()
    message.data = data
    return message


def _build_skill() -> AVAROSSkill:
    skill = AVAROSSkill()
    skill.log = Mock()
    skill.speak = Mock()
    skill.speak_dialog = Mock()
    skill.response_builder = Mock()
    skill._safe_dispatch = Mock(side_effect=lambda _name, action: action())
    skill._get_asset_registry = Mock(return_value=[])
    return skill


def test_canonicalize_asset_id_resolves_registry_alias() -> None:
    """Alias from asset registry should resolve to canonical asset_id."""
    skill = _build_skill()
    skill._get_asset_registry.return_value = [
        Asset(
            asset_id="line-1",
            display_name="Line 1",
            asset_type="line",
            aliases=["line one"],
        ),
    ]

    resolved = skill._canonicalize_asset_id("line one", raise_on_unknown=True)

    assert resolved == "line-1"


def test_canonicalize_asset_id_unknown_raises_with_suggestions() -> None:
    """Unknown slot asset should raise AssetNotFoundError with available assets."""
    skill = _build_skill()
    skill._get_asset_registry.return_value = [
        Asset(asset_id="Line-1", display_name="Line 1", asset_type="line"),
        Asset(asset_id="Compressor-1", display_name="Compressor 1", asset_type="machine"),
    ]

    with pytest.raises(AssetNotFoundError) as exc_info:
        skill._canonicalize_asset_id("CompressorABC", raise_on_unknown=True)

    error = exc_info.value
    assert error.asset_id == "CompressorABC"
    assert error.available_assets == ["Line 1", "Compressor 1"]
    assert "Available assets are" in error.user_message


def test_resolve_asset_id_returns_default_when_no_asset_slot() -> None:
    """No asset slot in utterance should keep default fallback behavior."""
    skill = _build_skill()

    resolved = skill._resolve_asset_id(_message(utterance="what is the energy"))

    assert resolved == "default"


def test_resolve_asset_id_raises_when_slot_present_but_unknown() -> None:
    """Detected asset slot should raise when it cannot be mapped."""
    skill = _build_skill()
    skill._get_asset_registry.return_value = [
        Asset(asset_id="Line-1", display_name="Line 1", asset_type="line"),
    ]

    with pytest.raises(AssetNotFoundError):
        skill._resolve_asset_id(_message(asset="Unknown line", utterance="energy for unknown line"))


def test_list_assets_handler_speaks_formatted_asset_list() -> None:
    """List-assets handler should format and speak discovered assets."""
    skill = _build_skill()
    assets = [
        Asset(asset_id="Line-1", display_name="Line 1", asset_type="line"),
        Asset(asset_id="Compressor-1", display_name="Compressor 1", asset_type="machine"),
    ]
    skill._get_asset_registry.return_value = assets
    skill.response_builder.format_asset_list.return_value = (
        "You have 2 assets configured: Line 1 and Compressor 1."
    )

    skill.handle_list_assets(_message(utterance="list assets"))

    skill.response_builder.format_asset_list.assert_called_once_with(["Line 1", "Compressor 1"])
    skill.speak.assert_called_once_with("You have 2 assets configured: Line 1 and Compressor 1.")
    skill.speak_dialog.assert_not_called()


def test_list_assets_handler_with_empty_registry_speaks_empty_message() -> None:
    """List-assets handler should give an honest no-assets response."""
    skill = _build_skill()
    skill._get_asset_registry.return_value = []

    skill.handle_list_assets(_message(utterance="what assets do I have"))

    skill.speak_dialog.assert_called_once_with("list.assets")
    skill.speak.assert_not_called()
