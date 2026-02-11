"""
CO₂ Derivation Service

Computes derived carbon metrics from energy consumption data
and configurable emission factors (DEC-023).

Design:
    - Pure computation, no I/O
    - Emission factors from SettingsService
    - Results as canonical KPIResult/TrendResult domain models
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from skill.domain.exceptions import ConfigurationError, ValidationError
from skill.domain.models import CanonicalMetric, DataPoint
from skill.domain.results import KPIResult, TrendResult

if TYPE_CHECKING:
    from skill.domain.models import TimePeriod
    from skill.services.settings import SettingsService


logger = logging.getLogger(__name__)


class CO2DerivationService:
    """Derives CO₂ metrics from energy data + configurable emission factors.

    Stateless — factors read from SettingsService on each call.
    """

    def __init__(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    def derive_co2_total(
        self, energy_kwh: float, energy_source: str,
        asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Derive co2_total = energy_kwh × emission_factor.

        Raises:
            ConfigurationError: If no emission factor configured.
        """
        factor = self._get_factor_or_raise(energy_source)
        co2_kg = round(energy_kwh * factor, 2)
        logger.info(
            "Derived co2_total=%.2f kg (%.2f kWh × %.4f %s)",
            co2_kg, energy_kwh, factor, energy_source,
        )
        return self._build_kpi(
            CanonicalMetric.CO2_TOTAL, co2_kg,
            "kg CO₂-eq", asset_id, period,
        )

    def derive_co2_per_unit(
        self, energy_kwh: float, production_count: int,
        energy_source: str, asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Derive co2_per_unit = (energy × factor) / count.

        Raises:
            ConfigurationError: If no emission factor configured.
            ValidationError: If production_count <= 0.
        """
        _validate_production_count(production_count)
        factor = self._get_factor_or_raise(energy_source)
        value = round((energy_kwh * factor) / production_count, 4)
        return self._build_kpi(
            CanonicalMetric.CO2_PER_UNIT, value,
            "kg CO₂-eq/unit", asset_id, period,
        )

    def derive_co2_trend(
        self, energy_data_points: tuple[DataPoint, ...],
        energy_source: str, asset_id: str,
        period: TimePeriod, granularity: str = "daily",
    ) -> TrendResult:
        """Derive CO₂ trend from energy time series."""
        factor = self._settings.get_effective_emission_factor(
            energy_source,
        )
        co2_points = _to_co2_points(energy_data_points, factor)
        direction, change_pct = self._compute_trend(co2_points)
        return TrendResult(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id=asset_id,
            data_points=co2_points,
            direction=direction,
            change_percent=change_pct,
            period=period,
            granularity=granularity,
        )

    @staticmethod
    def _compute_trend(
        points: tuple[DataPoint, ...],
    ) -> tuple[str, float]:
        """Compute trend direction and percentage change."""
        if len(points) < 2:
            return "stable", 0.0
        first, last = points[0].value, points[-1].value
        if first == 0:
            return ("up" if last > 0 else "stable"), 0.0
        change = round(((last - first) / first) * 100, 1)
        if change > 1.0:
            return "up", change
        if change < -1.0:
            return "down", change
        return "stable", change

    def _get_factor_or_raise(self, energy_source: str) -> float:
        """Get emission factor or raise ConfigurationError."""
        factor = self._settings.get_effective_emission_factor(
            energy_source,
        )
        if factor <= 0:
            raise ConfigurationError(
                message=f"No emission factor for '{energy_source}'",
                setting=f"emission_factor:{energy_source}",
            )
        return factor

    @staticmethod
    def _build_kpi(
        metric: CanonicalMetric, value: float,
        unit: str, asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Build a KPIResult for a CO₂ derived metric."""
        return KPIResult(
            metric=metric, value=value, unit=unit,
            asset_id=asset_id, period=period,
            timestamp=datetime.utcnow(),
        )


# ── Module-level helpers (stateless, no self) ──────────────────


def _validate_production_count(count: int) -> None:
    """Raise ValidationError if count <= 0."""
    if count <= 0:
        raise ValidationError(
            message=f"production_count must be > 0, got {count}",
            field="production_count",
            value=str(count),
        )


def _to_co2_points(
    points: tuple[DataPoint, ...], factor: float,
) -> tuple[DataPoint, ...]:
    """Multiply each energy data point by emission factor."""
    return tuple(
        DataPoint(
            timestamp=dp.timestamp,
            value=round(dp.value * factor, 2),
            unit="kg CO₂-eq",
        )
        for dp in points
    )
