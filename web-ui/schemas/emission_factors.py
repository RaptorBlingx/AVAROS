"""Request and response schemas for emission factor APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EnergySource = Literal["electricity", "gas", "water"]


class EmissionFactorRequest(BaseModel):
    """Create/update emission factor payload."""

    energy_source: EnergySource = Field(
        ...,
        description="Type of energy source.",
    )
    factor: float = Field(
        ...,
        gt=0,
        description="CO₂ emission factor (kg CO₂-eq per kWh or m³).",
    )
    country: str = Field(
        default="",
        max_length=10,
        description="Country code (e.g. 'TR', 'DE', 'EU').",
    )
    source: str = Field(
        default="",
        max_length=200,
        description="Citation for the factor value.",
    )
    year: int = Field(
        default=2024,
        ge=2000,
        le=2030,
        description="Reference year for the factor.",
    )


class EmissionFactorResponse(BaseModel):
    """Emission factor response."""

    energy_source: str
    factor: float
    country: str = ""
    source: str = ""
    year: int = 2024


class EmissionFactorListResponse(BaseModel):
    """List of emission factors."""

    factors: list[EmissionFactorResponse]


class EmissionFactorPresetResponse(BaseModel):
    """Country preset for emission factors."""

    country: str
    energy_source: str
    factor: float
    source: str = ""
    year: int = 2024
