"""Platform-agnostic asset discovery and mapping APIs."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

try:
    import websocket  # websocket-client
except ImportError:  # pragma: no cover
    websocket = None  # type: ignore[assignment]

from dependencies import get_adapter_factory, get_settings_service
from skill.adapters.factory import AdapterFactory
from skill.domain.exceptions import ValidationError
from skill.domain.models import Asset
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1", tags=["assets"])
logger = logging.getLogger(__name__)

MESSAGEBUS_URL = os.environ.get(
    "OVOS_MESSAGEBUS_URL", "ws://ovos_messagebus:8181/core",
)


class AssetItem(BaseModel):
    """Transport model for discovered/configured assets."""

    asset_id: str
    display_name: str
    asset_type: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetDiscoveryResponse(BaseModel):
    """Unified discovery payload for all platform types."""

    platform_type: str
    supports_discovery: bool
    assets: list[AssetItem] = Field(default_factory=list)
    existing_mappings: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AssetMappingsRequest(BaseModel):
    """Save payload for profile-scoped asset mappings."""

    asset_mappings: dict[str, dict[str, Any]]


class AssetMappingsResponse(BaseModel):
    """Response model for profile-scoped asset mappings."""

    asset_mappings: dict[str, dict[str, Any]]


def _notify_entity_refresh(profile_name: str) -> bool:
    """Emit best-effort entity refresh event to OVOS message bus."""
    if websocket is None:
        return False
    try:
        ws = websocket.create_connection(MESSAGEBUS_URL, timeout=3)
        payload = {
            "type": "avaros.entities.updated",
            "data": {"profile": profile_name},
            "context": {},
        }
        ws.send(json.dumps(payload))
        ws.close()
        return True
    except Exception as exc:
        logger.warning("Could not notify entity refresh via messagebus: %s", exc)
        return False


def _supports_discovery(platform_type: str) -> bool:
    """Return whether platform has live discovery support."""
    return platform_type.lower() in {"reneryo", "mock"}


def _serialize_asset(asset: Asset) -> AssetItem:
    """Convert domain Asset model to API transport model."""
    return AssetItem(
        asset_id=asset.asset_id,
        display_name=asset.display_name,
        asset_type=asset.asset_type,
        aliases=asset.aliases,
        metadata=asset.metadata,
    )


def _get_current_platform(settings_service: SettingsService) -> str:
    """Resolve active profile platform type."""
    profile_name = settings_service.get_active_profile_name()
    profile = settings_service.get_profile(profile_name)
    if profile is None:
        return "mock"
    return str(profile.platform_type or "mock").lower()


def _persist_asset_mappings(
    payload: AssetMappingsRequest,
    settings_service: SettingsService,
) -> AssetMappingsResponse:
    """Save mappings and trigger asset entity refresh event."""
    try:
        settings_service.set_asset_mappings(payload.asset_mappings)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    _notify_entity_refresh(settings_service.get_active_profile_name())
    return AssetMappingsResponse(
        asset_mappings=settings_service.get_asset_mappings(),
    )


@router.get("/assets/mappings", response_model=AssetMappingsResponse)
def get_asset_mappings(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Legacy endpoint returning current profile asset mappings."""
    return AssetMappingsResponse(
        asset_mappings=settings_service.get_asset_mappings(),
    )


@router.put("/assets/mappings", response_model=AssetMappingsResponse)
def put_asset_mappings(
    payload: AssetMappingsRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Legacy endpoint for updating profile-scoped asset mappings."""
    return _persist_asset_mappings(payload, settings_service)


@router.get("/config/assets", response_model=AssetMappingsResponse)
def get_config_assets(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Return profile-scoped asset mappings for settings/wizard UI."""
    return AssetMappingsResponse(
        asset_mappings=settings_service.get_asset_mappings(),
    )


@router.post("/config/assets", response_model=AssetMappingsResponse)
def post_config_assets(
    payload: AssetMappingsRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Persist profile-scoped asset mappings for all platform types."""
    return _persist_asset_mappings(payload, settings_service)


@router.get("/assets/discover", response_model=AssetDiscoveryResponse)
async def discover_assets(
    settings_service: SettingsService = Depends(get_settings_service),
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
) -> AssetDiscoveryResponse:
    """Discover assets through active adapter's list_assets() implementation."""
    platform_type = _get_current_platform(settings_service)
    adapter = adapter_factory.create()
    discovered_assets: list[Asset] = []

    try:
        await adapter.initialize()
        discovered_assets = await adapter.list_assets()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Asset discovery failed for '{platform_type}': {exc}",
        ) from exc
    finally:
        try:
            await adapter.shutdown()
        except Exception as exc:  # pragma: no cover - defensive shutdown path
            logger.warning("Adapter shutdown after asset discovery failed: %s", exc)

    items = [_serialize_asset(asset) for asset in discovered_assets if isinstance(asset, Asset)]
    return AssetDiscoveryResponse(
        platform_type=platform_type,
        supports_discovery=_supports_discovery(platform_type),
        assets=items,
        existing_mappings=settings_service.get_asset_mappings(),
    )
