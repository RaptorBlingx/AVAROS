"""
Emission Factor Domain Models

CO₂ emission factors for deriving carbon metrics from energy data.
Part of the AVAROS domain layer — platform-agnostic, immutable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmissionFactor:
    """CO₂ emission factor for an energy source.

    Attributes:
        energy_source: Type of energy (electricity, gas, water)
        factor: kg CO₂-eq per kWh (or per m³ for gas)
        unit: Always "kg_co2_per_kwh" or "kg_co2_per_m3"
        country: Country/region this factor applies to
        source: Citation for the factor value
        year: Reference year for the factor
    """

    energy_source: str
    factor: float
    unit: str = "kg_co2_per_kwh"
    country: str = ""
    source: str = ""
    year: int = 2024


# Default emission factors by country and energy source.
# Türkiye (TR) is primary pilot site; DE and EU for reference.
DEFAULT_EMISSION_FACTORS: dict[str, dict[str, EmissionFactor]] = {
    "TR": {
        "electricity": EmissionFactor(
            energy_source="electricity",
            factor=0.48,
            country="TR",
            source="TEDAŞ / IEA 2024",
            year=2024,
        ),
        "gas": EmissionFactor(
            energy_source="gas",
            factor=0.20,
            unit="kg_co2_per_kwh",
            country="TR",
            source="IPCC default",
            year=2024,
        ),
    },
    "DE": {
        "electricity": EmissionFactor(
            energy_source="electricity",
            factor=0.38,
            country="DE",
            source="Umweltbundesamt 2024",
            year=2024,
        ),
        "gas": EmissionFactor(
            energy_source="gas",
            factor=0.20,
            unit="kg_co2_per_kwh",
            country="DE",
            source="IPCC default",
            year=2024,
        ),
    },
    "EU": {
        "electricity": EmissionFactor(
            energy_source="electricity",
            factor=0.26,
            country="EU",
            source="EEA 2024",
            year=2024,
        ),
        "gas": EmissionFactor(
            energy_source="gas",
            factor=0.20,
            unit="kg_co2_per_kwh",
            country="EU",
            source="IPCC default",
            year=2024,
        ),
    },
}
