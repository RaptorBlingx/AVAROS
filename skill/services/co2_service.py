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
    """
    Derives CO₂-equivalent metrics from energy consumption data.

    Uses configurable emission factors to compute:
    - co2_total = energy_total × emission_factor
    - co2_per_unit = co2_total / production_count (when available)

    The service is stateless — emission factors are read from
    SettingsService on each call for freshness.

    Attributes:
        _settings: SettingsService for reading emission factors
    """

    def __init__(self, settings_service: SettingsService) -> None:
        """Initialize with a SettingsService.

        Args:
            settings_service: Service for reading emission factors
        """
        self._settings = settings_service

    def derive_co2_total(
        self,
        energy_kwh: float,
        energy_source: str,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """Derive co2_total from energy consumption.

        Formula: co2_total = energy_kwh × emission_factor

        Args:
            energy_kwh: Total energy consumed in kWh
            energy_source: "electricity" or "gas"
            asset_id: Asset identifier
            period: Time period of the measurement

        Returns:
            KPIResult with metric=CO2_TOTAL, value in kg CO₂-eq

        Raises:
            ConfigurationError: If no emission factor is configured
        """
        factor = self._get_factor_or_raise(energy_source)
        co2_kg = round(energy_kwh * factor, 2)

        logger.info(
            "Derived co2_total=%.2f kg from %.2f kWh × %.4f factor (%s)",
            co2_kg, energy_kwh, factor, energy_source,
        )

        return KPIResult(
            metric=CanonicalMetric.CO2_TOTAL,
            value=co2_kg,
            unit="kg CO₂-eq",
            asset_id=asset_id,
            period=period,
            timestamp=datetime.utcnow(),
        )

    def derive_co2_per_unit(
        self,
        energy_kwh: float,
        production_count: int,
        energy_source: str,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """Derive co2_per_unit from energy and production count.

        Formula: co2_per_unit = (energy_kwh × emission_factor) / production_count

        Args:
            energy_kwh: Total energy consumed in kWh
            production_count: Number of units produced (> 0)
            energy_source: "electricity" or "gas"
            asset_id: Asset identifier
            period: Time period

        Returns:
            KPIResult with metric=CO2_PER_UNIT, value in kg CO₂-eq/unit

        Raises:
            ConfigurationError: If no emission factor configured
            ValidationError: If production_count <= 0
        """
        if production_count <= 0:
            raise ValidationError(
                message=f"production_count must be > 0, got {production_count}",
                field="production_count",
                value=str(production_count),
            )

        factor = self._get_factor_or_raise(energy_source)
        co2_total = energy_kwh * factor
        co2_per_unit = round(co2_total / production_count, 4)

        return KPIResult(
            metric=CanonicalMetric.CO2_PER_UNIT,
            value=co2_per_unit,
            unit="kg CO₂-eq/unit",
            asset_id=asset_id,
            period=period,
            timestamp=datetime.utcnow(),
        )

    def derive_co2_trend(
        self,
        energy_data_points: tuple[DataPoint, ...],
        energy_source: str,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """Derive CO₂ trend from energy consumption time series.

        Each energy data point (kWh) is multiplied by the emission
        factor to produce a CO₂ data point (kg CO₂-eq).

        Args:
            energy_data_points: Energy consumption data points
            energy_source: "electricity" or "gas"
            asset_id: Asset identifier
            period: Time period
            granularity: Data point frequency

        Returns:
            TrendResult with CO₂ data points and trend direction
        """
        factor = self._settings.get_effective_emission_factor(
            energy_source,
        )

        co2_points = tuple(
            DataPoint(
                timestamp=dp.timestamp,
                value=round(dp.value * factor, 2),
                unit="kg CO₂-eq",
            )
            for dp in energy_data_points
        )

        direction, change_percent = self._compute_trend(co2_points)

        return TrendResult(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id=asset_id,
            data_points=co2_points,
            direction=direction,
            change_percent=change_percent,
            period=period,
            granularity=granularity,
        )

    @staticmethod
    def _compute_trend(
        points: tuple[DataPoint, ...],
    ) -> tuple[str, float]:
        """Compute trend direction and percentage change.

        Args:
            points: Ordered data points (earliest first)

        Returns:
            Tuple of (direction, change_percent):
            - direction: "up", "down", or "stable"
            - change_percent: percentage change from first to last
        """
        if len(points) < 2:
            return "stable", 0.0

        first = points[0].value
        last = points[-1].value

        if first == 0:
            return ("up" if last > 0 else "stable"), 0.0

        change = ((last - first) / first) * 100
        change = round(change, 1)

        if change > 1.0:
            return "up", change
        elif change < -1.0:
            return "down", change
        return "stable", change

    def _get_factor_or_raise(self, energy_source: str) -> float:
        """Get emission factor or raise ConfigurationError.

        Args:
            energy_source: "electricity" or "gas"

        Returns:
            Emission factor value (> 0)

        Raises:
            ConfigurationError: If no factor configured for source
        """
        factor = self._settings.get_effective_emission_factor(
            energy_source,
        )
        if factor <= 0:
            raise ConfigurationError(
                message=(
                    f"No emission factor configured for "
                    f"'{energy_source}'"
                ),
                setting=f"emission_factor:{energy_source}",
            )
        return factor
