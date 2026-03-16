"""Slot-based asset resolution for voice message handling.

Resolves asset IDs from intent parser slots, utterance text fallbacks,
and configured defaults. Includes noise-word filtering to discard
mis-parsed slot values that aren't real asset references.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from skill.domain.exceptions import AssetNotFoundError
from skill.domain.models import Asset

if TYPE_CHECKING:
    from ovos_bus_client.message import Message

# ── Noise detection constants ─────────────────────────

_NOISE_WORDS = frozenset({"to", "too", "for", "on", "line", "trend"})
_NOISE_SLOT_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "check",
        "compare",
        "for",
        "give",
        "how",
        "i",
        "in",
        "is",
        "me",
        "on",
        "please",
        "show",
        "tell",
        "the",
        "to",
        "too",
        "trend",
        "what",
        "which",
    },
)
_NOISE_SLOT_PREFIXES = (
    "check ",
    "compare ",
    "give ",
    "how ",
    "show ",
    "tell ",
    "trend ",
    "what ",
    "which ",
)


def _is_noisy_asset_slot(slot_value: str) -> bool:
    """Return True when parser produced non-asset phrase in asset slot."""
    normalized = re.sub(r"[^a-z0-9\s-]", " ", slot_value.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return True
    if normalized in _NOISE_WORDS:
        return True
    if normalized.startswith(_NOISE_SLOT_PREFIXES):
        return True

    tokens = normalized.replace("-", " ").split()
    if len(tokens) >= 2 and all(token in _NOISE_SLOT_WORDS for token in tokens):
        return True
    return False


# ── Line asset extraction ─────────────────────────────


def extract_line_assets_from_text(self, text: str) -> list[str]:
    """Extract spoken line assets from utterance text (e.g., line two)."""
    if not text:
        return []

    matches = re.findall(
        r"\bline\s+(1|2|3|4|5|one|two|three|four|five|to|too)\b",
        text.lower(),
    )
    line_token_to_digit = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "to": "2",
        "too": "2",
    }
    return [
        f"Line-{line_token_to_digit.get(value, value)}"
        for value in matches
    ]


# ── Asset resolution from message slots ───────────────


def resolve_asset_id(self, message: Message, default: str = "default") -> str:
    """Resolve asset_id using slot first, then utterance fallback parsing."""
    data = getattr(message, "data", {}) or {}
    slot_value = str(data.get("asset", "")).strip()

    utterance_text = self._extract_utterance_text(message)
    if slot_value and not _is_noisy_asset_slot(slot_value):
        try:
            slot_asset = self._canonicalize_asset_id(
                slot_value,
                raise_on_unknown=True,
            )
            return slot_asset
        except AssetNotFoundError:
            utterance_assets = self._extract_line_assets_from_text(utterance_text)
            if utterance_assets:
                return utterance_assets[0]
            raise

    utterance_assets = self._extract_line_assets_from_text(utterance_text)
    if utterance_assets:
        return utterance_assets[0]

    alias_match = self._canonicalize_asset_id(utterance_text)
    if alias_match and alias_match != utterance_text:
        return alias_match

    return _resolve_default_asset_id(self, fallback=default)


def resolve_compare_assets(self, message: Message) -> tuple[str, str]:
    """Resolve comparison assets with utterance fallback for line references."""
    data = getattr(message, "data", {}) or {}
    raw_a = str(data.get("asset_a", "")).strip()
    raw_b = str(data.get("asset_b", "")).strip()
    asset_a = (
        self._canonicalize_asset_id(raw_a)
        if raw_a and not _is_noisy_asset_slot(raw_a)
        else ""
    )
    asset_b = (
        self._canonicalize_asset_id(raw_b)
        if raw_b and not _is_noisy_asset_slot(raw_b)
        else ""
    )
    if asset_a and asset_b:
        return asset_a, asset_b

    utterance_assets = self._extract_line_assets_from_text(
        self._extract_utterance_text(message)
    )
    if len(utterance_assets) >= 2:
        return utterance_assets[0], utterance_assets[1]

    default_pair = _resolve_default_compare_assets(self)
    if default_pair is not None:
        default_a, default_b = default_pair
        resolved_a = asset_a or default_a
        resolved_b = asset_b or (default_b if default_b != resolved_a else default_a)
        if resolved_a and resolved_b and resolved_a != resolved_b:
            return resolved_a, resolved_b

    return asset_a or "Asset-1", asset_b or "Asset-2"


# ── Default asset resolution ─────────────────────────


def _resolve_default_compare_assets(self) -> tuple[str, str] | None:
    """Choose two sensible defaults for compare when slots are missing."""
    settings_service = getattr(self, "settings_service", None)
    if settings_service is not None:
        try:
            mappings = settings_service.get_asset_mappings()
        except Exception:
            mappings = {}
        if isinstance(mappings, dict):
            asset_ids = [str(key).strip() for key in mappings.keys() if str(key).strip()]
            if len(asset_ids) >= 2:
                ordered = sorted(asset_ids)
                return ordered[0], ordered[1]

    try:
        assets = self._get_asset_registry()
    except Exception:
        assets = []

    seen: list[str] = []
    for asset in assets:
        if not isinstance(asset, Asset):
            continue
        asset_id = str(asset.asset_id).strip()
        if asset_id and asset_id not in seen:
            seen.append(asset_id)
    if len(seen) >= 2:
        return seen[0], seen[1]
    return None


def _resolve_default_asset_id(self, *, fallback: str) -> str:
    """Choose default asset id from configured mappings/registry when possible."""
    settings_service = getattr(self, "settings_service", None)
    if settings_service is not None:
        try:
            mappings = settings_service.get_asset_mappings()
        except Exception:
            mappings = {}
        if isinstance(mappings, dict):
            asset_ids = sorted(
                str(key).strip()
                for key in mappings.keys()
                if str(key).strip()
            )
            if asset_ids:
                return asset_ids[0]

    try:
        assets = list(self._get_asset_registry())
    except Exception:
        assets = []
    registry_ids = sorted(
        str(getattr(asset, "asset_id", "")).strip()
        for asset in assets
        if str(getattr(asset, "asset_id", "")).strip()
    )
    if registry_ids:
        return registry_ids[0]

    return fallback
