"""
Tests for PreventionClient interface and MockPreventionClient.

Model immutability, drift, and helper tests in test_prevention_models.py.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from skill.clients.base import ExternalServiceClient
from skill.clients.prevention import (
    MockPreventionClient,
    PreventionClient,
)
from skill.domain.anomaly_models import AnomalyDetectionResult
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


class TestPreventionClientInterface:
    """Verify MockPreventionClient implements required interfaces."""

    def test_is_external_service_client(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """MockPreventionClient must be an ExternalServiceClient."""
        assert isinstance(mock_client, ExternalServiceClient)

    def test_is_prevention_client(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """MockPreventionClient must be a PreventionClient."""
        assert isinstance(mock_client, PreventionClient)


class TestMockPreventionLifecycle:
    """Test ExternalServiceClient lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_sets_connected(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """initialize() should set is_connected to True."""
        assert not mock_client.is_connected
        await mock_client.initialize()
        assert mock_client.is_connected

    @pytest.mark.asyncio
    async def test_shutdown_clears_connected(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """shutdown() should set is_connected to False."""
        await mock_client.initialize()
        await mock_client.shutdown()
        assert not mock_client.is_connected

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """shutdown() must be safe to call multiple times."""
        await mock_client.shutdown()
        await mock_client.shutdown()
        assert not mock_client.is_connected

    @pytest.mark.asyncio
    async def test_health_check_always_true(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """health_check() returns True for mock."""
        assert await mock_client.health_check() is True

    def test_service_name_is_string(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """service_name must return a non-empty string."""
        assert isinstance(mock_client.service_name, str)
        assert len(mock_client.service_name) > 0

    def test_service_name_platform_agnostic(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """service_name must not contain platform-specific names (DEC-001)."""
        name_lower = mock_client.service_name.lower()
        assert "prevention" not in name_lower

    @pytest.mark.asyncio
    async def test_reinitialize_after_shutdown(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """Client can be re-initialized after shutdown."""
        await mock_client.initialize()
        await mock_client.shutdown()
        await mock_client.initialize()
        assert mock_client.is_connected


class TestMockPreventionDetectAnomaly:
    """Test detect_anomaly() method."""

    @pytest.mark.asyncio
    async def test_returns_anomaly_detection_result(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """detect_anomaly() must return an AnomalyDetectionResult."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert isinstance(result, AnomalyDetectionResult)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", [
        CanonicalMetric.ENERGY_PER_UNIT,
        CanonicalMetric.PEAK_DEMAND,
    ])
    async def test_anomalous_metrics_detected(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
        metric: CanonicalMetric,
    ) -> None:
        """Energy and peak demand must be anomalous in demo."""
        result = await mock_client.detect_anomaly(metric, sample_data_points)
        assert result.is_anomalous is True
        assert result.severity == "medium"
        assert result.anomaly_type == "spike"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metric", [
        CanonicalMetric.SCRAP_RATE,
        CanonicalMetric.OEE,
    ])
    async def test_non_anomalous_metrics_normal(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
        metric: CanonicalMetric,
    ) -> None:
        """Non-anomalous demo metrics must show normal."""
        result = await mock_client.detect_anomaly(metric, sample_data_points)
        assert result.is_anomalous is False
        assert result.severity == "none"
        assert result.anomaly_type is None

    @pytest.mark.asyncio
    async def test_confidence_is_valid_range(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Confidence must be between 0.0 and 1.0."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_description_is_non_empty(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Description must be a non-empty string."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert isinstance(result.description, str)
        assert len(result.description) > 10

    @pytest.mark.asyncio
    async def test_anomalous_has_recommended_action(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Anomalous results must include a recommended action."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert result.recommended_action is not None
        assert len(result.recommended_action) > 0

    @pytest.mark.asyncio
    async def test_normal_has_no_recommended_action(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Normal results must have no recommended action."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.SCRAP_RATE,
            sample_data_points,
        )
        assert result.recommended_action is None

    @pytest.mark.asyncio
    async def test_detected_at_is_iso_timestamp(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """detected_at must be a valid ISO 8601 timestamp."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        # Should not raise ValueError
        datetime.fromisoformat(result.detected_at)

    @pytest.mark.asyncio
    async def test_detected_at_uses_last_data_point(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """detected_at should use the last data point's timestamp."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        expected = sample_data_points[-1].timestamp.isoformat()
        assert result.detected_at == expected

    @pytest.mark.asyncio
    async def test_empty_data_points_still_works(
        self, mock_client: MockPreventionClient,
    ) -> None:
        """detect_anomaly() handles empty data point list."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            [],
        )
        assert isinstance(result, AnomalyDetectionResult)

    @pytest.mark.asyncio
    async def test_metric_preserved_in_result(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Result must carry the original metric."""
        result = await mock_client.detect_anomaly(
            CanonicalMetric.CO2_PER_UNIT,
            sample_data_points,
        )
        assert result.metric is CanonicalMetric.CO2_PER_UNIT

    @pytest.mark.asyncio
    async def test_deterministic_same_input_same_output(
        self,
        mock_client: MockPreventionClient,
        sample_data_points: list[DataPoint],
    ) -> None:
        """Same metric must produce identical results (deterministic)."""
        result_a = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        result_b = await mock_client.detect_anomaly(
            CanonicalMetric.ENERGY_PER_UNIT,
            sample_data_points,
        )
        assert result_a == result_b
