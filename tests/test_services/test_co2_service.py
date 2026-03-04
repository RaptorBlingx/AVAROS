"""
CO2DerivationService Unit Test Suite

Covers all public methods:
    - derive_co2_total (basic, zero energy, gas, result type, no factor, stored factor)
    - derive_co2_per_unit (basic, zero production, negative production)
    - derive_co2_trend (basic, direction up/down, single point, empty)
    - _compute_trend (up, down, stable, zero baseline)

Uses a real SettingsService with in-memory SQLite.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from skill.domain.exceptions import ConfigurationError, ValidationError
from skill.domain.models import CanonicalMetric, DataPoint, TimePeriod
from skill.domain.results import KPIResult, TrendResult
from skill.services.co2_service import CO2DerivationService
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


# ── Fixtures ──────────────────────────────────────────


@pytest.fixture
def settings_service() -> SettingsService:
    """In-memory SettingsService, initialized and ready."""
    svc = SettingsService()
    svc.initialize()
    return svc


@pytest.fixture
def co2_service(settings_service: SettingsService) -> CO2DerivationService:
    """CO2DerivationService with default TR emission factors."""
    return CO2DerivationService(settings_service)


@pytest.fixture
def co2_service_no_factors() -> CO2DerivationService:
    """CO2DerivationService with no emission factors at all.

    Uses a SettingsService where get_effective_emission_factor returns 0.0
    for any source (no stored factors, no defaults for the requested source).
    """
    svc = SettingsService()
    svc.initialize()
    # We'll request "solar" which has no default
    return CO2DerivationService(svc)


@pytest.fixture
def period() -> TimePeriod:
    """Standard test time period."""
    return TimePeriod.today()


# ══════════════════════════════════════════════════════════
# 1. derive_co2_total
# ══════════════════════════════════════════════════════════


class TestDeriveCO2Total:
    """Tests for derive_co2_total()."""

    def test_basic_calculation(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """100 kWh × 0.48 factor = 48.0 kg CO₂."""
        result = co2_service.derive_co2_total(
            energy_kwh=100.0,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.value == 48.0

    def test_zero_energy(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """0 kWh → 0.0 kg CO₂."""
        result = co2_service.derive_co2_total(
            energy_kwh=0.0,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.value == 0.0

    def test_gas_factor(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Gas factor (0.20) applied instead of electricity."""
        result = co2_service.derive_co2_total(
            energy_kwh=100.0,
            energy_source="gas",
            asset_id="Line-1",
            period=period,
        )
        assert result.value == 20.0

    def test_returns_kpi_result(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Result is a KPIResult with metric=CO2_TOTAL."""
        result = co2_service.derive_co2_total(
            energy_kwh=100.0,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.CO2_TOTAL
        assert result.unit == "kg CO₂-eq"
        assert result.asset_id == "Line-1"

    def test_no_factor_raises(
        self, co2_service_no_factors: CO2DerivationService,
        period: TimePeriod,
    ) -> None:
        """Raises ConfigurationError when no factor configured."""
        with pytest.raises(ConfigurationError):
            co2_service_no_factors.derive_co2_total(
                energy_kwh=100.0,
                energy_source="solar",
                asset_id="Line-1",
                period=period,
            )

    def test_uses_stored_factor(
        self, settings_service: SettingsService, period: TimePeriod,
    ) -> None:
        """Custom stored factor overrides default."""
        settings_service.create_profile(
            "reneryo",
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.example.com",
                api_key="secret",
                extra_settings={"auth_type": "cookie"},
            ),
        )
        settings_service.set_active_profile("reneryo")
        settings_service.set_emission_factor("electricity", 0.55)
        svc = CO2DerivationService(settings_service)
        result = svc.derive_co2_total(
            energy_kwh=100.0,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.value == 55.0


# ══════════════════════════════════════════════════════════
# 2. derive_co2_per_unit
# ══════════════════════════════════════════════════════════


class TestDeriveCO2PerUnit:
    """Tests for derive_co2_per_unit()."""

    def test_basic_calculation(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """100 kWh × 0.48 / 10 units = 4.8 kg/unit."""
        result = co2_service.derive_co2_per_unit(
            energy_kwh=100.0,
            production_count=10,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.value == 4.8
        assert result.metric == CanonicalMetric.CO2_PER_UNIT

    def test_zero_production_raises(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Raises ValidationError when production_count=0."""
        with pytest.raises(ValidationError):
            co2_service.derive_co2_per_unit(
                energy_kwh=100.0,
                production_count=0,
                energy_source="electricity",
                asset_id="Line-1",
                period=period,
            )

    def test_negative_production_raises(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Raises ValidationError when production_count < 0."""
        with pytest.raises(ValidationError):
            co2_service.derive_co2_per_unit(
                energy_kwh=100.0,
                production_count=-5,
                energy_source="electricity",
                asset_id="Line-1",
                period=period,
            )


# ══════════════════════════════════════════════════════════
# 3. derive_co2_trend
# ══════════════════════════════════════════════════════════


class TestDeriveCO2Trend:
    """Tests for derive_co2_trend()."""

    def test_basic_trend(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Each energy data point multiplied by factor."""
        points = (
            DataPoint(datetime(2026, 2, 1), 100.0, "kWh"),
            DataPoint(datetime(2026, 2, 2), 100.0, "kWh"),
        )
        result = co2_service.derive_co2_trend(
            energy_data_points=points,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, TrendResult)
        assert result.metric == CanonicalMetric.CO2_TOTAL
        assert len(result.data_points) == 2
        assert result.data_points[0].value == 48.0
        assert result.data_points[1].value == 48.0

    def test_direction_up(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Increasing energy → increasing CO₂ trend."""
        points = (
            DataPoint(datetime(2026, 2, 1), 100.0, "kWh"),
            DataPoint(datetime(2026, 2, 2), 200.0, "kWh"),
        )
        result = co2_service.derive_co2_trend(
            energy_data_points=points,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.direction == "up"
        assert result.change_percent > 0

    def test_direction_down(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Decreasing energy → decreasing CO₂ trend."""
        points = (
            DataPoint(datetime(2026, 2, 1), 200.0, "kWh"),
            DataPoint(datetime(2026, 2, 2), 100.0, "kWh"),
        )
        result = co2_service.derive_co2_trend(
            energy_data_points=points,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.direction == "down"
        assert result.change_percent < 0

    def test_single_point_stable(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Single data point → stable trend."""
        points = (DataPoint(datetime(2026, 2, 1), 100.0, "kWh"),)
        result = co2_service.derive_co2_trend(
            energy_data_points=points,
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.direction == "stable"

    def test_empty_points_stable(
        self, co2_service: CO2DerivationService, period: TimePeriod,
    ) -> None:
        """Empty data points → stable trend."""
        result = co2_service.derive_co2_trend(
            energy_data_points=(),
            energy_source="electricity",
            asset_id="Line-1",
            period=period,
        )
        assert result.direction == "stable"
        assert len(result.data_points) == 0


# ══════════════════════════════════════════════════════════
# 4. _compute_trend (static method)
# ══════════════════════════════════════════════════════════


class TestComputeTrend:
    """Tests for _compute_trend() static method."""

    def test_up(self) -> None:
        """Change > 1% → 'up'."""
        points = (
            DataPoint(datetime(2026, 2, 1), 100.0),
            DataPoint(datetime(2026, 2, 2), 110.0),
        )
        direction, change = CO2DerivationService._compute_trend(points)
        assert direction == "up"
        assert change == 10.0

    def test_down(self) -> None:
        """Change < -1% → 'down'."""
        points = (
            DataPoint(datetime(2026, 2, 1), 100.0),
            DataPoint(datetime(2026, 2, 2), 90.0),
        )
        direction, change = CO2DerivationService._compute_trend(points)
        assert direction == "down"
        assert change == -10.0

    def test_stable(self) -> None:
        """Change between -1% and 1% → 'stable'."""
        points = (
            DataPoint(datetime(2026, 2, 1), 100.0),
            DataPoint(datetime(2026, 2, 2), 100.5),
        )
        direction, change = CO2DerivationService._compute_trend(points)
        assert direction == "stable"

    def test_zero_baseline(self) -> None:
        """First point = 0 → 'up' if nonzero last, else 'stable'."""
        points = (
            DataPoint(datetime(2026, 2, 1), 0.0),
            DataPoint(datetime(2026, 2, 2), 50.0),
        )
        direction, change = CO2DerivationService._compute_trend(points)
        assert direction == "up"
        assert change == 0.0

    def test_zero_baseline_zero_last(self) -> None:
        """First=0, last=0 → 'stable'."""
        points = (
            DataPoint(datetime(2026, 2, 1), 0.0),
            DataPoint(datetime(2026, 2, 2), 0.0),
        )
        direction, change = CO2DerivationService._compute_trend(points)
        assert direction == "stable"
        assert change == 0.0
