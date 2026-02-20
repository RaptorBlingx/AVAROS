"""Asset discovery and mapping APIs for RENERYO native integration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from dependencies import get_settings_service
from skill.adapters.reneryo import ReneryoAdapter
from skill.adapters.reneryo._endpoints import (
    REAL_METRIC_NAMES_ENDPOINT,
    REAL_METRIC_RESOURCES_ENDPOINT,
    REAL_SEU_NAMES_ENDPOINT,
)
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


class DiscoveredSeu(BaseModel):
    id: str
    name: str
    energy_resource: str = ""


class MetricCandidate(BaseModel):
    key: str
    id: str = ""
    name: str = ""


class MetricResourceOption(BaseModel):
    id: str
    name: str


class AssetDiscoveryResponse(BaseModel):
    seus: list[DiscoveredSeu] = Field(default_factory=list)
    metrics: list[MetricCandidate] = Field(default_factory=list)
    resources: dict[str, list[MetricResourceOption]] = Field(default_factory=dict)
    existing_mappings: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AssetMappingsRequest(BaseModel):
    asset_mappings: dict[str, dict[str, Any]]


class AssetMappingsResponse(BaseModel):
    asset_mappings: dict[str, dict[str, Any]]


def _select_metric(records: list[dict[str, Any]], key: str) -> tuple[str, str]:
    needle = "oee" if key == "oee" else "scrap"
    for record in records:
        name = str(record.get("name", ""))
        if needle in name.lower():
            return str(record.get("id", "")), name
    return "", ""


@router.get("/mappings", response_model=AssetMappingsResponse)
def get_asset_mappings(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Return saved asset mappings used by RENERYO adapter."""
    return AssetMappingsResponse(asset_mappings=settings_service.get_asset_mappings())


@router.put("/mappings", response_model=AssetMappingsResponse)
def put_asset_mappings(
    payload: AssetMappingsRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetMappingsResponse:
    """Persist asset mappings and sync platform extra settings."""
    settings_service.set_asset_mappings(payload.asset_mappings)
    return AssetMappingsResponse(asset_mappings=settings_service.get_asset_mappings())


@router.get("/discover", response_model=AssetDiscoveryResponse)
async def discover_assets(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AssetDiscoveryResponse:
    """Discover SEUs and production metric resources from RENERYO."""
    config = settings_service.get_platform_config()
    if config.platform_type != "reneryo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset discovery is available only for RENERYO profiles.",
        )
    if not config.api_url or not config.api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="RENERYO api_url and api_key must be configured before discovery.",
        )

    extra = config.extra_settings if isinstance(config.extra_settings, dict) else {}
    adapter = ReneryoAdapter(
        api_url=config.api_url,
        api_key=config.api_key,
        auth_type=str(extra.get("auth_type", "bearer")),
        api_format=str(extra.get("api_format", "native") or "native"),
        asset_mappings=settings_service.get_asset_mappings(),
    )

    try:
        await adapter.initialize()

        seus_payload = await adapter._retry_fetch(REAL_SEU_NAMES_ENDPOINT)
        metric_names_payload = await adapter._retry_fetch(REAL_METRIC_NAMES_ENDPOINT)

        seu_records = seus_payload.get("records", []) if isinstance(seus_payload, dict) else []
        metric_records = (
            metric_names_payload.get("records", [])
            if isinstance(metric_names_payload, dict)
            else []
        )

        metrics: list[MetricCandidate] = []
        resources: dict[str, list[MetricResourceOption]] = {"oee": [], "scrap_rate": []}

        for key in ("oee", "scrap_rate"):
            metric_id, metric_name = _select_metric(metric_records, key)
            metrics.append(MetricCandidate(key=key, id=metric_id, name=metric_name))
            if not metric_id:
                continue
            response = await adapter._retry_fetch(
                REAL_METRIC_RESOURCES_ENDPOINT,
                {"metricId": metric_id},
            )
            resource_records = response.get("records", []) if isinstance(response, dict) else []
            resources[key] = [
                MetricResourceOption(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                )
                for item in resource_records
                if item.get("id")
            ]

        seus = [
            DiscoveredSeu(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                energy_resource=str(item.get("energyResource", "")),
            )
            for item in seu_records
            if item.get("id")
        ]

        return AssetDiscoveryResponse(
            seus=seus,
            metrics=metrics,
            resources=resources,
            existing_mappings=settings_service.get_asset_mappings(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RENERYO discovery failed: {exc}",
        ) from exc
    finally:
        await adapter.shutdown()
