"""Asset registry loading and spoken-asset canonicalization helpers."""

from __future__ import annotations

import difflib
import re
from typing import TYPE_CHECKING, Any

from skill.domain.exceptions import AssetNotFoundError
from skill.domain.models import Asset

if TYPE_CHECKING:
    from skill import AVAROSSkill


_LINE_SYNONYM_TO_DIGIT = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "to": "2",
    "too": "2",
}
_VALID_ASSET_TYPES = {"machine", "line", "sensor", "seu"}


def get_asset_registry(
    skill: "AVAROSSkill",
    *,
    force_refresh: bool = False,
) -> list[Asset]:
    """Return cached assets for active profile, loading from adapter/settings."""
    profile = skill._resolve_active_profile()
    cached_profile = getattr(skill, "_asset_registry_profile", "")
    cached_assets = getattr(skill, "_asset_registry_cache", None)
    if not force_refresh and isinstance(cached_assets, list) and cached_profile == profile:
        return cached_assets

    assets = _load_assets_from_adapter(skill)
    settings_assets = _load_assets_from_settings(skill, profile)
    if settings_assets:
        existing_ids = {a.asset_id for a in assets}
        for sa in settings_assets:
            if sa.asset_id not in existing_ids:
                assets.append(sa)

    skill._asset_registry_cache = assets
    skill._asset_registry_profile = profile
    return assets


def resolve_asset_id_from_text(
    skill: "AVAROSSkill",
    raw_asset: str,
    *,
    raise_on_unknown: bool,
) -> str:
    """Resolve spoken asset text into canonical asset_id."""
    token = (raw_asset or "").strip()
    if not token:
        return ""

    assets = skill._get_asset_registry()
    fast_path_asset = _resolve_line_fast_path(token, assets)
    if fast_path_asset is not None:
        return fast_path_asset

    matched_asset = _match_asset_from_registry(token, assets)
    if matched_asset is not None:
        return matched_asset.asset_id

    if raise_on_unknown:
        display_names = [asset.display_name for asset in assets][:10]
        user_message = _build_asset_not_found_message(display_names)
        raise AssetNotFoundError(
            message="",
            asset_id=token,
            available_assets=display_names,
            user_message=user_message,
        )

    return token


def _load_assets_from_adapter(skill: "AVAROSSkill") -> list[Asset]:
    """Load asset registry from active adapter."""
    dispatcher = getattr(skill, "dispatcher", None)
    adapter = getattr(dispatcher, "adapter", None) if dispatcher else None
    if adapter is None or not hasattr(adapter, "list_assets"):
        return []

    try:
        loaded = dispatcher._run_async(adapter.list_assets())
    except Exception as exc:
        skill.log.warning("Asset discovery failed on adapter.list_assets(): %s", exc)
        return []

    if not isinstance(loaded, list):
        return []
    return [asset for asset in loaded if isinstance(asset, Asset)]


def _load_assets_from_settings(
    skill: "AVAROSSkill",
    profile: str,
) -> list[Asset]:
    """Load assets from SettingsService cache as fallback."""
    settings_service = getattr(skill, "settings_service", None)
    if settings_service is None or not hasattr(settings_service, "get_asset_list"):
        return []

    try:
        rows = settings_service.get_asset_list(profile=profile)
    except Exception as exc:
        skill.log.warning("Asset discovery failed on SettingsService.get_asset_list(): %s", exc)
        return []

    assets: list[Asset] = []
    for row in rows:
        asset = _asset_from_settings_row(row)
        if asset is not None:
            assets.append(asset)
    return assets


def _asset_from_settings_row(row: Any) -> Asset | None:
    """Convert settings row into Asset, skipping invalid rows."""
    if not isinstance(row, dict):
        return None

    asset_id = str(row.get("asset_id", "")).strip()
    if not asset_id:
        return None

    display_name = str(row.get("display_name") or asset_id).strip()
    aliases_raw = row.get("aliases", [])
    aliases = [str(item).strip() for item in aliases_raw if str(item).strip()] if isinstance(aliases_raw, list) else []
    metadata = row.get("metadata", {})
    asset_type = str(row.get("asset_type") or "machine").strip().lower()
    if asset_type not in _VALID_ASSET_TYPES:
        asset_type = "machine"

    try:
        return Asset(
            asset_id=asset_id,
            display_name=display_name,
            asset_type=asset_type,
            aliases=aliases,
            metadata=metadata if isinstance(metadata, dict) else {},
        )
    except ValueError:
        return None


def _resolve_line_fast_path(token: str, assets: list[Asset]) -> str | None:
    """Resolve frequent 'line N' phrases with fast-path lookup."""
    normalized = re.sub(r"[-_]+", " ", token.lower()).strip()
    line_match = re.fullmatch(
        r"line\s+(1|2|3|4|5|one|two|three|four|five|to|too)",
        normalized,
    )
    if not line_match:
        return None

    suffix_raw = line_match.group(1)
    suffix = _LINE_SYNONYM_TO_DIGIT.get(suffix_raw, suffix_raw)
    candidate_id = f"Line-{suffix}"
    if not assets:
        return candidate_id

    for asset in assets:
        if asset.asset_id.lower() == candidate_id.lower():
            return asset.asset_id
    return None


def _match_asset_from_registry(token: str, assets: list[Asset]) -> Asset | None:
    """Match by exact alias/display name, then fuzzy fallback."""
    if not assets:
        return None

    query_key = _normalize_key(token)
    if not query_key:
        return None

    lookup = _build_lookup(assets)
    exact = lookup.get(query_key)
    if exact is not None:
        return exact

    if len(query_key) >= 3:
        for candidate_key, candidate_asset in lookup.items():
            if len(candidate_key) >= 3 and (
                query_key in candidate_key or candidate_key in query_key
            ):
                return candidate_asset

    close = difflib.get_close_matches(query_key, lookup.keys(), n=1, cutoff=0.82)
    if close:
        return lookup[close[0]]
    return None


def _build_lookup(assets: list[Asset]) -> dict[str, Asset]:
    """Build normalized alias/name lookup table."""
    lookup: dict[str, Asset] = {}
    for asset in assets:
        variants = [asset.asset_id, asset.display_name, *asset.aliases]
        for variant in variants:
            key = _normalize_key(variant)
            if key and key not in lookup:
                lookup[key] = asset
    return lookup


def _normalize_key(text: str) -> str:
    """Normalize free-form text for case/whitespace/punctuation-insensitive match."""
    lowered = text.lower().strip()
    lowered = lowered.replace("-", " ").replace("_", " ")
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _build_asset_not_found_message(display_names: list[str]) -> str:
    """Build user-facing message with registry-backed suggestions."""
    if not display_names:
        return (
            "I couldn't find that asset. "
            "No assets are configured yet. You can add assets in the Web UI settings."
        )
    return (
        "I couldn't find that asset. Available assets are: "
        f"{', '.join(display_names)}."
    )
