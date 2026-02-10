"""
Tests for anomaly models (DEC-004 immutability), drift monitoring,
and prevention helper functions.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from skill.clients.prevention import (
    MockPreventionClient,
    _build_anomaly_description,
    _get_category_for_metric,
    _get_recommended_action,
    _is_metric_anomalous,
)
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport
from skill.domain.models import CanonicalMetric, DataPoint


@pytest.fixture
def mock_client() -> MockPreventionClient:
    """Create a fresh MockPreventionClient for each test."""
    return MockPreventionClient()


@pytest.fixture
def sample_data_points() -> list[DataPoint]:
    """Create sample time-series data points for testing."""
    base = datetime(2026, 2, 10, 8, 0, 0)
    return [
        DataPoint(
            timestamp=datetime(
                base.year, base.month, base.day, base.hour + i,
            ),
            value=2.5 + (i * 0.1),
            unit="kWh/unit",
        )
        for i in range(5)
    ]


class TestMockPreventionCheckDrift:
    """Test check_drift() method."""

    @pytest.mark.asyncio
    async def test_returns_drift_report(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """check_drift() must return a DriftReport."""
        result = await mock_client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert isinstance(result, DriftReport)

    @pytest.mark.asyncio
    async def test_energy_drift_improving(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Energy metrics should show improving drift."""
        result = await mock_client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert result.has_drift is True
        assert result.drift_direction == "improving"
        assert result.drift_rate < 0

    @pytest.mark.asyncio
    async def test_scrap_drift_stable(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Material metrics should show stable drift."""
        result = await mock_client.check_drift(
            CanonicalMetric.SCRAP_RATE,
            sample_data_points,
        )
        assert result.has_drift is False
        assert result.drift_direction == "stable"
        assert result.drift_rate == 0.0

    @pytest.mark.asyncio
    async def test_supplier_drift_degrading(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Supplier metrics should show degrading drift."""
        result = await mock_client.check_drift(
            CanonicalMetric.SUPPLIER_LEAD_TIME,
            sample_data_points,
        )
        assert result.has_drift is True
        assert result.drift_direction == "degrading"
        assert result.drift_rate > 0

    @pytest.mark.asyncio
    async def test_periods_preserved_in_result(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """periods_analyzed must match the periods argument."""
        result = await mock_client.check_drift(
            CanonicalMetric.OEE,
            sample_data_points,
            periods=14,
        )
        assert result.periods_analyzed == 14

    @pytest.mark.asyncio
    async def test_metric_preserved_in_result(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Result must carry the original metric."""
        result = await mock_client.check_drift(
            CanonicalMetric.CO2_TOTAL,
            sample_data_points,
        )
        assert result.metric is CanonicalMetric.CO2_TOTAL

    @pytest.mark.asyncio
    async def test_description_is_non_empty(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Drift description must be a non-empty string."""
        result = await mock_client.check_drift(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert isinstance(result.description, str)
        assert len(result.description) > 10

    @pytest.mark.asyncio
    async def test_production_drift_improving(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Production metrics should show improving drift."""
        result = await mock_client.check_drift(
            CanonicalMetric.OEE,
            sample_data_points,
        )
        assert result.has_drift is True
        assert result.drift_direction == "improving"


class TestAnomalyModelImmutability:
    """Verify domain models are frozen (DEC-004)."""

    def test_anomaly_detection_result_frozen(self) -> None:
        """AnomalyDetectionResult must be immutable."""
        result = AnomalyDetectionResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            is_anomalous=True,
            severity="medium",
            confidence=0.85,
            anomaly_type="spike",
            description="Test anomaly",
            detected_at="2026-02-10T14:30:00Z",
            recommended_action="Check equipment",
        )
        with pytest.raises(AttributeError):
            result.severity = "high"  # type: ignore[misc]

    def test_anomaly_detection_result_fields(self) -> None:
        """AnomalyDetectionResult must expose all required fields."""
        result = AnomalyDetectionResult(
            metric=CanonicalMetric.SCRAP_RATE,
            is_anomalous=False,
            severity="none",
            confidence=0.85,
            anomaly_type=None,
            description="Normal operation",
            detected_at="2026-02-10T14:30:00Z",
            recommended_action=None,
        )
        assert result.metric is CanonicalMetric.SCRAP_RATE
        assert result.is_anomalous is False
        assert result.severity == "none"
        assert result.confidence == 0.85
        assert result.anomaly_type is None
        assert result.recommended_action is None

    def test_drift_report_frozen(self) -> None:
        """DriftReport must be immutable."""
        report = DriftReport(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            has_drift=True,
            drift_direction="improving",
            drift_rate=-0.3,
            periods_analyzed=7,
            description="Test drift",
        )
        with pytest.raises(AttributeError):
            report.drift_rate = 0.0  # type: ignore[misc]

    def test_drift_report_fields(self) -> None:
        """DriftReport must expose all required fields."""
        report = DriftReport(
            metric=CanonicalMetric.OEE,
            has_drift=True,
            drift_direction="improving",
            drift_rate=0.5,
            periods_analyzed=14,
            description="OEE improving",
        )
        assert report.metric is CanonicalMetric.OEE
        assert report.has_drift is True
        assert report.drift_direction == "improving"
        assert report.drift_rate == 0.5
        assert report.periods_analyzed == 14

    def test_frozen_models_support_equality(self) -> None:
        """Identical frozen instances must be equal."""
        adr_kwargs = {
            "metric": CanonicalMetric.ENERGY_PER_UNIT,
            "is_anomalous": True, "severity": "medium",
            "confidence": 0.85, "anomaly_type": "spike",
            "description": "Test", "detected_at": "2026-02-10T14:30:00Z",
            "recommended_action": "Fix it",
        }
        assert AnomalyDetectionResult(**adr_kwargs) == AnomalyDetectionResult(**adr_kwargs)
        dr_kwargs = {
            "metric": CanonicalMetric.OEE, "has_drift": True,
            "drift_direction": "improving", "drift_rate": 0.5,
            "periods_analyzed": 7, "description": "Test",
        }
        assert DriftReport(**dr_kwargs) == DriftReport(**dr_kwargs)


class TestPreventionHelpers:
    """Test helper functions used by MockPreventionClient."""

    @pytest.mark.parametrize(("metric", "expected"), [
        (CanonicalMetric.ENERGY_PER_UNIT, "energy"),
        (CanonicalMetric.PEAK_DEMAND, "energy"),
        (CanonicalMetric.SCRAP_RATE, "material"),
        (CanonicalMetric.REWORK_RATE, "material"),
        (CanonicalMetric.CO2_PER_UNIT, "carbon"),
        (CanonicalMetric.OEE, "production"),
        (CanonicalMetric.SUPPLIER_LEAD_TIME, "supplier"),
    ])
    def test_get_category_for_metric(
        self, metric: CanonicalMetric, expected: str,
    ) -> None:
        """Each metric maps to the correct category."""
        assert _get_category_for_metric(metric) == expected

    @pytest.mark.parametrize(("metric", "expected"), [
        (CanonicalMetric.ENERGY_PER_UNIT, True),
        (CanonicalMetric.SCRAP_RATE, False),
    ])
    def test_is_metric_anomalous(
        self, metric: CanonicalMetric, expected: bool,
    ) -> None:
        """Verify anomalous demo set membership."""
        assert _is_metric_anomalous(metric) is expected

    def test_build_anomaly_description_anomalous(self) -> None:
        """Anomalous description includes deviation value."""
        desc = _build_anomaly_description("energy", True, 2.3)
        assert "2.3" in desc
        assert len(desc) > 20

    def test_build_anomaly_description_normal(self) -> None:
        """Normal description indicates no anomaly."""
        desc = _build_anomaly_description("energy", False, 0.8)
        assert "normal" in desc.lower() or "within" in desc.lower()

    def test_get_recommended_action_anomalous(self) -> None:
        """Anomalous metrics should have a recommended action."""
        action = _get_recommended_action("energy", True)
        assert action is not None
        assert len(action) > 10

    def test_get_recommended_action_normal(self) -> None:
        """Normal metrics should have no recommended action."""
        action = _get_recommended_action("energy", False)
        assert action is None
