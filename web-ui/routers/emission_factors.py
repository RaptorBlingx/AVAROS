"""Emission factor configuration API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_settings_service
from schemas.emission_factors import (
    EmissionFactorListResponse,
    EmissionFactorPresetResponse,
    EmissionFactorRequest,
    EmissionFactorResponse,
)
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["emission-factors"])


@router.get(
    "/emission-factors",
    response_model=EmissionFactorListResponse,
)
def list_emission_factors(
    settings_service: SettingsService = Depends(get_settings_service),
) -> EmissionFactorListResponse:
    """List all configured emission factors."""
    factors = settings_service.list_emission_factors()
    return EmissionFactorListResponse(
        factors=[
            EmissionFactorResponse(
                energy_source=data["energy_source"],
                factor=data["factor"],
                country=data.get("country", ""),
                source=data.get("source", ""),
                year=data.get("year", 2024),
            )
            for data in factors.values()
        ],
    )


@router.post(
    "/emission-factors",
    response_model=EmissionFactorResponse,
)
def set_emission_factor(
    payload: EmissionFactorRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> EmissionFactorResponse:
    """Create or update an emission factor."""
    settings_service.set_emission_factor(
        energy_source=payload.energy_source,
        factor=payload.factor,
        country=payload.country,
        source=payload.source,
        year=payload.year,
    )
    return EmissionFactorResponse(
        energy_source=payload.energy_source,
        factor=payload.factor,
        country=payload.country,
        source=payload.source,
        year=payload.year,
    )


@router.delete("/emission-factors/{energy_source}")
def delete_emission_factor(
    energy_source: str,
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict[str, str]:
    """Delete an emission factor."""
    deleted = settings_service.delete_emission_factor(energy_source)
    if not deleted:
        raise HTTPException(status_code=404, detail="Factor not found")
    return {"status": "deleted", "energy_source": energy_source}


@router.get(
    "/emission-factors/presets",
    response_model=list[EmissionFactorPresetResponse],
)
def list_presets() -> list[EmissionFactorPresetResponse]:
    """List available country presets for emission factors."""
    from skill.domain.models import DEFAULT_EMISSION_FACTORS

    presets: list[EmissionFactorPresetResponse] = []
    for country, sources in DEFAULT_EMISSION_FACTORS.items():
        for source_name, ef in sources.items():
            presets.append(
                EmissionFactorPresetResponse(
                    country=country,
                    energy_source=source_name,
                    factor=ef.factor,
                    source=ef.source,
                    year=ef.year,
                ),
            )
    return presets
