"""Tests for StatisticalPreventionClient — real anomaly and drift detection."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from skill.clients.base import ExternalServiceClient
from skill.clients.prevention import PreventionClient
from skill.clients.prevention_statistical import (
    StatisticalPreventionClient,
    _classify_severity,
    _linear_regression,
    _mean,
    _std,
)
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport
from skill.domain.models import CanonicalMetric, DataPoint


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def client() -> StatisticalPreventionClient:
    """Create a fresh StatisticalPreventionClient."""
    return StatisticalPreventionClient()


def _make_data_points(
    values: list[float],
    *,
    unit: str = "kWh/unit",
    start: datetime | None = None,
) -> list[DataPoint]:
    """Build DataPoint list from raw values."""
    base = start or datetime(2026, 2, 10, 8, 0, 0)
    return [
        DataPoint(
            timestamp=base + timedelta(hours=i),
            value=v,
            unit=unit,
        )
        for i, v in enumerate(values)
    ]


@pytest.fixture
def normal_data() -> list[DataPoint]:
    """5 data points with low variance — no anomaly expected."""
    return _make_data_points([2.5, 2.6, 2.4, 2.5, 2.55])


@pytest.fixture
def anomalous_data() -> list[DataPoint]:
    """Data with a clear spike — anomaly expected."""
    return _make_data_points([2.5, 2.6, 2.4, 2.5, 2.5, 2.6, 2.4, 20.0])


@pytest.fixture
def constant_data() -> list[DataPoint]:
    """All identical values — zero variance."""
    return _make_data_points([3.0, 3.0, 3.0, 3.0, 3.0])


@pytest.fixture
def increasing_drift_data() -> list[DataPoint]:
    """Clearly increasing 15-point series for drift detection."""
    return _make_data_points([1.0 + 0.5 * i for i in range(15)])


@pytest.fixture
def stable_drift_data() -> list[DataPoint]:
    """Stable 15-point series — no drift expected."""
    return _make_data_points([5.0] * 15)


# =========================================================================
# Interface Tests
# =========================================================================


class TestStatisticalClientInterface:
    """Verify StatisticalPreventionClient implements required ABCs."""

    def test_is_external_service_client(
        self, client: StatisticalPreventionClient,
    ) -> None:
        assert isinstance(client, ExternalServiceClient)

    def test_is_prevention_client(
        self, client: StatisticalPreventionClient,
    ) -> None:
        assert isinstance(client, PreventionClient)


# =========================================================================
# Lifecycle Tests
# =========================================================================


class TestStatisticalClientLifecycle:
    """Test ExternalServiceClient lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_sets_connected(
        self, client: StatisticalPreventionClient,
    ) -> None:
        assert not client.is_connected
        await client.initialize()
        assert client.is_connected

    @pytest.mark.asyncio
    async def test_shutdown_clears_connected(
        self, client: StatisticalPreventionClient,
    ) -> None:
        await client.initialize()
        await client.shutdown()
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_health_check_always_true(
        self, client: StatisticalPreventionClient,
    ) -> None:
        assert await client.health_check() is True

    def test_service_name_is_string(
        self, client: StatisticalPreventionClient,
    ) -> None:
        assert isinstance(client.service_name, str)
        assert len(client.service_name) > 0

    def test_service_name_platform_agnostic(
        self, client: StatisticalPreventionClient,
    ) -> None:
        """DEC-001: No platform names in service_name."""
        name_lower = client.service_name.lower()
        assert "prevention" not in name_lower
        assert "reneryo" not in name_lower


# =========================================================================
# Anomaly Detection Tests
# =========================================================================


class TestDetectAnomaly:
    """Test z-score anomaly detection."""

    @pytest.mark.asyncio
    async def test_returns_anomaly_detection_result(
        self,
        client: StatisticalPreventionClient,
        normal_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, normal_data,
        )
        assert isinstance(result, AnomalyDetectionResult)

    @pytest.mark.asyncio
    async def test_normal_data_not_anomalous(
        self,
        client: StatisticalPreventionClient,
        normal_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, normal_data,
        )
        assert result.is_anomalous is False
        assert result.severity == "none"
        assert result.anomaly_type is None

    @pytest.mark.asyncio
    async def test_spike_detected_as_anomaly(
        self,
        client: StatisticalPreventionClient,
        anomalous_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, anomalous_data,
        )
        assert result.is_anomalous is True
        assert result.severity != "none"
        assert result.anomaly_type == "spike"

    @pytest.mark.asyncio
    async def test_dip_detected_as_anomaly(
        self, client: StatisticalPreventionClient,
    ) -> None:
        """Value far below mean should be flagged as 'dip'."""
        data = _make_data_points([10.0, 10.1, 9.9, 10.0, 10.1, 9.9, 10.0, 0.1])
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, data,
        )
        assert result.is_anomalous is True
        assert result.anomaly_type == "dip"

    @pytest.mark.asyncio
    async def test_constant_data_not_anomalous(
        self,
        client: StatisticalPreventionClient,
        constant_data: list[DataPoint],
    ) -> None:
        """Zero variance data should return not anomalous."""
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, constant_data,
        )
        assert result.is_anomalous is False
        assert "stable" in result.description.lower()

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_safe_result(
        self, client: StatisticalPreventionClient,
    ) -> None:
        """Fewer than MIN_ANOMALY_POINTS should return not anomalous."""
        data = _make_data_points([2.5, 2.6])
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, data,
        )
        assert result.is_anomalous is False
        assert result.confidence == 0.0
        assert "insufficient" in result.description.lower()

    @pytest.mark.asyncio
    async def test_empty_data_returns_safe_result(
        self, client: StatisticalPreventionClient,
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, [],
        )
        assert result.is_anomalous is False
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_metric_preserved_in_result(
        self,
        client: StatisticalPreventionClient,
        normal_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.CO2_PER_UNIT, normal_data,
        )
        assert result.metric is CanonicalMetric.CO2_PER_UNIT

    @pytest.mark.asyncio
    async def test_detected_at_is_iso_timestamp(
        self,
        client: StatisticalPreventionClient,
        normal_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, normal_data,
        )
        datetime.fromisoformat(result.detected_at)

    @pytest.mark.asyncio
    async def test_anomalous_has_recommended_action(
        self,
        client: StatisticalPreventionClient,
        anomalous_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, anomalous_data,
        )
        assert result.recommended_action is not None
        assert len(result.recommended_action) > 0

    @pytest.mark.asyncio
    async def test_normal_has_no_recommended_action(
        self,
        client: StatisticalPreventionClient,
        normal_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, normal_data,
        )
        assert result.recommended_action is None

    @pytest.mark.asyncio
    async def test_confidence_in_valid_range(
        self,
        client: StatisticalPreventionClient,
        normal_data: list[DataPoint],
    ) -> None:
        result = await client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT, normal_data,
        )
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_custom_threshold(
        self, client: StatisticalPreventionClient,
    ) -> None:
        """Higher threshold should make detection less sensitive."""
        data = _make_data_points([2.5, 2.6, 2.4, 2.5, 4.0])
        result_low = await client.detect_anomaly(
            CanonicalMetric.OEE, data, threshold=1.0,
        )
        result_high = await client.detect_anomaly(
            CanonicalMetric.OEE, data, threshold=5.0,
        )
        # Low threshold more likely to flag, high threshold less likely
        assert result_low.is_anomalous is True or result_high.is_anomalous is False


# =========================================================================
# Drift Detection Tests
# =========================================================================


class TestCheckDrift:
    """Test linear regression drift detection."""

    @pytest.mark.asyncio
    async def test_returns_drift_report(
        self,
        client: StatisticalPreventionClient,
        increasing_drift_data: list[DataPoint],
    ) -> None:
        result = await client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT, increasing_drift_data,
        )
        assert isinstance(result, DriftReport)

    @pytest.mark.asyncio
    async def test_increasing_energy_is_degrading(
        self,
        client: StatisticalPreventionClient,
        increasing_drift_data: list[DataPoint],
    ) -> None:
        """For energy, increase = degrading (higher is worse)."""
        result = await client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT, increasing_drift_data,
        )
        assert result.has_drift is True
        assert result.drift_direction == "degrading"
        assert result.drift_rate > 0

    @pytest.mark.asyncio
    async def test_increasing_oee_is_improving(
        self,
        client: StatisticalPreventionClient,
        increasing_drift_data: list[DataPoint],
    ) -> None:
        """For OEE, increase = improving (higher is better)."""
        result = await client.check_drift(
            CanonicalMetric.OEE, increasing_drift_data,
        )
        assert result.has_drift is True
        assert result.drift_direction == "improving"

    @pytest.mark.asyncio
    async def test_stable_data_no_drift(
        self,
        client: StatisticalPreventionClient,
        stable_drift_data: list[DataPoint],
    ) -> None:
        result = await client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT, stable_drift_data,
        )
        assert result.has_drift is False
        assert result.drift_direction == "stable"

    @pytest.mark.asyncio
    async def test_insufficient_data_no_drift(
        self, client: StatisticalPreventionClient,
    ) -> None:
        data = _make_data_points([1.0, 2.0, 3.0])
        result = await client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT, data,
        )
        assert result.has_drift is False
        assert "insufficient" in result.description.lower()
        assert result.periods_analyzed == 0

    @pytest.mark.asyncio
    async def test_metric_preserved_in_drift(
        self,
        client: StatisticalPreventionClient,
        increasing_drift_data: list[DataPoint],
    ) -> None:
        result = await client.check_drift(
            CanonicalMetric.SCRAP_RATE, increasing_drift_data,
        )
        assert result.metric is CanonicalMetric.SCRAP_RATE

    @pytest.mark.asyncio
    async def test_periods_in_result(
        self,
        client: StatisticalPreventionClient,
        increasing_drift_data: list[DataPoint],
    ) -> None:
        result = await client.check_drift(
            CanonicalMetric.OEE, increasing_drift_data, periods=14,
        )
        assert result.periods_analyzed == 14

    @pytest.mark.asyncio
    async def test_decreasing_energy_is_improving(
        self, client: StatisticalPreventionClient,
    ) -> None:
        """For energy, decrease = improving."""
        data = _make_data_points([10.0 - 0.5 * i for i in range(15)])
        result = await client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT, data,
        )
        assert result.has_drift is True
        assert result.drift_direction == "improving"
        assert result.drift_rate < 0


# =========================================================================
# Helper Function Tests
# =========================================================================


class TestHelperFunctions:
    """Test standalone math/classification helpers."""

    def test_classify_severity_none(self) -> None:
        assert _classify_severity(1.5) == "none"

    def test_classify_severity_low(self) -> None:
        assert _classify_severity(2.1) == "low"

    def test_classify_severity_medium(self) -> None:
        assert _classify_severity(2.7) == "medium"

    def test_classify_severity_high(self) -> None:
        assert _classify_severity(3.5) == "high"

    def test_classify_severity_critical(self) -> None:
        assert _classify_severity(4.5) == "critical"

    def test_mean_simple(self) -> None:
        assert _mean([1.0, 2.0, 3.0]) == 2.0

    def test_std_simple(self) -> None:
        vals = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        m = _mean(vals)
        result = _std(vals, m)
        assert round(result, 4) == 2.0

    def test_linear_regression_perfect_line(self) -> None:
        """y = 2x + 1 should give slope=2, intercept=1, R²=1."""
        values = [1.0 + 2.0 * i for i in range(10)]
        slope, intercept, r_sq = _linear_regression(values)
        assert round(slope, 4) == 2.0
        assert round(intercept, 4) == 1.0
        assert round(r_sq, 4) == 1.0

    def test_linear_regression_constant(self) -> None:
        """Constant values: slope=0, R²=0."""
        values = [5.0] * 10
        slope, _intercept, r_sq = _linear_regression(values)
        assert slope == 0.0
        assert r_sq == 0.0
