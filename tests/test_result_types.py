"""
Result Type Unit Tests

Tests for canonical manufacturing result types (KPIResult, ComparisonResult, etc.).
Validates type construction, immutability, serialization, and properties.
"""

import pytest
from datetime import datetime, timedelta

from skill.domain.models import (
    CanonicalMetric,
    TimePeriod,
    DataPoint,
    Anomaly,
)
from skill.domain.results import (
    KPIResult,
    ComparisonItem,
    ComparisonResult,
    TrendResult,
    AnomalyResult,
    WhatIfResult,
    ConnectionTestResult,
)


class TestKPIResult:
    """Tests for KPIResult dataclass."""
    
    def test_creation_with_all_fields_creates_result(self):
        """Test creating KPIResult with all required fields."""
        # Arrange
        metric = CanonicalMetric.ENERGY_PER_UNIT
        value = 45.2
        unit = "kWh/unit"
        asset_id = "Compressor-1"
        period = TimePeriod.today()
        timestamp = datetime.now()
        
        # Act
        result = KPIResult(
            metric=metric,
            value=value,
            unit=unit,
            asset_id=asset_id,
            period=period,
            timestamp=timestamp
        )
        
        # Assert
        assert result.metric == metric
        assert result.value == value
        assert result.unit == unit
        assert result.asset_id == asset_id
        assert result.period == period
        assert result.timestamp == timestamp
    
    def test_creation_with_recommendation_id_stores_id(self):
        """Test creating KPIResult with recommendation ID."""
        # Arrange
        recommendation_id = "rec-12345"
        
        # Act
        result = KPIResult(
            metric=CanonicalMetric.OEE,
            value=82.5,
            unit="%",
            asset_id="Line-1",
            period=TimePeriod.today(),
            timestamp=datetime.now(),
            recommendation_id=recommendation_id
        )
        
        # Assert
        assert result.recommendation_id == recommendation_id
    
    def test_immutability_prevents_field_mutation(self):
        """Test that KPIResult is immutable."""
        # Arrange
        result = KPIResult(
            metric=CanonicalMetric.OEE,
            value=82.5,
            unit="%",
            asset_id="Line-1",
            period=TimePeriod.today(),
            timestamp=datetime.now()
        )
        
        # Act & Assert
        with pytest.raises((AttributeError, Exception)):
            result.value = 99.9
    
    def test_to_dict_serializes_all_fields(self):
        """Test to_dict serializes result to dictionary."""
        # Arrange
        timestamp = datetime(2026, 2, 8, 10, 30, 0)
        period = TimePeriod.today()
        result = KPIResult(
            metric=CanonicalMetric.SCRAP_RATE,
            value=2.5,
            unit="%",
            asset_id="Line-1",
            period=period,
            timestamp=timestamp,
            recommendation_id="rec-001"
        )
        
        # Act
        result_dict = result.to_dict()
        
        # Assert
        assert result_dict["metric"] == "scrap_rate"
        assert result_dict["value"] == 2.5
        assert result_dict["unit"] == "%"
        assert result_dict["asset_id"] == "Line-1"
        assert "period_start" in result_dict
        assert "period_end" in result_dict
        assert result_dict["timestamp"] == timestamp.isoformat()
        assert result_dict["recommendation_id"] == "rec-001"
    
    def test_formatted_value_with_percentage_formats_correctly(self):
        """Test formatted_value property with percentage unit."""
        # Arrange
        result = KPIResult(
            metric=CanonicalMetric.OEE,
            value=82.567,
            unit="%",
            asset_id="Line-1",
            period=TimePeriod.today(),
            timestamp=datetime.now()
        )
        
        # Act
        formatted = result.formatted_value
        
        # Assert
        assert formatted == "82.6%"
    
    def test_formatted_value_with_unit_formats_correctly(self):
        """Test formatted_value property with non-percentage unit."""
        # Arrange
        result = KPIResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            value=45.234,
            unit="kWh/unit",
            asset_id="Compressor-1",
            period=TimePeriod.today(),
            timestamp=datetime.now()
        )
        
        # Act
        formatted = result.formatted_value
        
        # Assert
        assert formatted == "45.23 kWh/unit"


class TestComparisonItem:
    """Tests for ComparisonItem dataclass."""
    
    def test_creation_with_all_fields_creates_item(self):
        """Test creating ComparisonItem with all fields."""
        # Arrange
        asset_id = "Compressor-1"
        value = 2.3
        rank = 1
        
        # Act
        item = ComparisonItem(
            asset_id=asset_id,
            value=value,
            rank=rank
        )
        
        # Assert
        assert item.asset_id == asset_id
        assert item.value == value
        assert item.rank == rank
    
    def test_immutability_prevents_field_mutation(self):
        """Test that ComparisonItem is immutable."""
        # Arrange
        item = ComparisonItem(asset_id="Test", value=1.0, rank=1)
        
        # Act & Assert
        with pytest.raises((AttributeError, Exception)):
            item.rank = 2


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""
    
    def test_creation_with_list_converts_to_tuple(self):
        """Test creating ComparisonResult converts items list to tuple."""
        # Arrange
        items = [
            ComparisonItem("Compressor-1", 2.3, 1),
            ComparisonItem("Compressor-2", 2.8, 2)
        ]
        
        # Act
        result = ComparisonResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            items=items,
            winner_id="Compressor-1",
            difference=0.5,
            unit="kWh/unit",
            period=TimePeriod.today()
        )
        
        # Assert
        assert isinstance(result.items, tuple)
        assert len(result.items) == 2
    
    def test_creation_with_tuple_stores_tuple(self):
        """Test creating ComparisonResult with tuple works."""
        # Arrange
        items = (
            ComparisonItem("Line-1", 85.0, 1),
            ComparisonItem("Line-2", 80.0, 2)
        )
        
        # Act
        result = ComparisonResult(
            metric=CanonicalMetric.OEE,
            items=items,
            winner_id="Line-1",
            difference=5.0,
            unit="%",
            period=TimePeriod.this_week()
        )
        
        # Assert
        assert result.items == items
    
    def test_immutability_prevents_field_mutation(self):
        """Test that ComparisonResult is immutable."""
        # Arrange
        items = [ComparisonItem("Test", 1.0, 1)]
        result = ComparisonResult(
            metric=CanonicalMetric.OEE,
            items=items,
            winner_id="Test",
            difference=0.0,
            unit="%",
            period=TimePeriod.today()
        )
        
        # Act & Assert
        with pytest.raises((AttributeError, Exception)):
            result.winner_id = "Other"
    
    def test_get_value_for_asset_with_existing_asset_returns_value(self):
        """Test get_value_for_asset returns value for existing asset."""
        # Arrange
        items = [
            ComparisonItem("Asset-1", 10.0, 1),
            ComparisonItem("Asset-2", 20.0, 2),
            ComparisonItem("Asset-3", 30.0, 3)
        ]
        result = ComparisonResult(
            metric=CanonicalMetric.THROUGHPUT,
            items=items,
            winner_id="Asset-3",
            difference=20.0,
            unit="units/hr",
            period=TimePeriod.today()
        )
        
        # Act
        value = result.get_value_for_asset("Asset-2")
        
        # Assert
        assert value == 20.0
    
    def test_get_value_for_asset_with_missing_asset_returns_none(self):
        """Test get_value_for_asset returns None for missing asset."""
        # Arrange
        items = [ComparisonItem("Asset-1", 10.0, 1)]
        result = ComparisonResult(
            metric=CanonicalMetric.OEE,
            items=items,
            winner_id="Asset-1",
            difference=0.0,
            unit="%",
            period=TimePeriod.today()
        )
        
        # Act
        value = result.get_value_for_asset("NonExistent")
        
        # Assert
        assert value is None


class TestTrendResult:
    """Tests for TrendResult dataclass."""
    
    def test_creation_with_list_converts_to_tuple(self):
        """Test creating TrendResult converts data_points list to tuple."""
        # Arrange
        data_points = [
            DataPoint(datetime(2026, 2, 1), 10.0, "kWh"),
            DataPoint(datetime(2026, 2, 2), 12.0, "kWh"),
            DataPoint(datetime(2026, 2, 3), 11.0, "kWh")
        ]
        
        # Act
        result = TrendResult(
            metric=CanonicalMetric.ENERGY_TOTAL,
            asset_id="Line-1",
            data_points=data_points,
            direction="stable",
            change_percent=5.0,
            period=TimePeriod.last_week(),
            granularity="daily"
        )
        
        # Assert
        assert isinstance(result.data_points, tuple)
        assert len(result.data_points) == 3
    
    def test_immutability_prevents_field_mutation(self):
        """Test that TrendResult is immutable."""
        # Arrange
        data_points = [DataPoint(datetime.now(), 10.0, "%")]
        result = TrendResult(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            data_points=data_points,
            direction="up",
            change_percent=5.0,
            period=TimePeriod.last_week(),
            granularity="daily"
        )
        
        # Act & Assert
        with pytest.raises((AttributeError, Exception)):
            result.direction = "down"
    
    def test_start_value_with_data_returns_first_value(self):
        """Test start_value property returns first data point value."""
        # Arrange
        data_points = [
            DataPoint(datetime(2026, 2, 1), 100.0, "%"),
            DataPoint(datetime(2026, 2, 2), 95.0, "%")
        ]
        result = TrendResult(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            data_points=data_points,
            direction="down",
            change_percent=-5.0,
            period=TimePeriod.today(),
            granularity="hourly"
        )
        
        # Act
        start = result.start_value
        
        # Assert
        assert start == 100.0
    
    def test_end_value_with_data_returns_last_value(self):
        """Test end_value property returns last data point value."""
        # Arrange
        data_points = [
            DataPoint(datetime(2026, 2, 1), 100.0, "%"),
            DataPoint(datetime(2026, 2, 2), 95.0, "%")
        ]
        result = TrendResult(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            data_points=data_points,
            direction="down",
            change_percent=-5.0,
            period=TimePeriod.today(),
            granularity="hourly"
        )
        
        # Act
        end = result.end_value
        
        # Assert
        assert end == 95.0
    
    def test_min_value_with_data_returns_minimum(self):
        """Test min_value property returns minimum value."""
        # Arrange
        data_points = [
            DataPoint(datetime(2026, 2, 1), 100.0, "%"),
            DataPoint(datetime(2026, 2, 2), 85.0, "%"),
            DataPoint(datetime(2026, 2, 3), 95.0, "%")
        ]
        result = TrendResult(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            data_points=data_points,
            direction="stable",
            change_percent=-5.0,
            period=TimePeriod.last_week(),
            granularity="daily"
        )
        
        # Act
        minimum = result.min_value
        
        # Assert
        assert minimum == 85.0
    
    def test_max_value_with_data_returns_maximum(self):
        """Test max_value property returns maximum value."""
        # Arrange
        data_points = [
            DataPoint(datetime(2026, 2, 1), 100.0, "%"),
            DataPoint(datetime(2026, 2, 2), 85.0, "%"),
            DataPoint(datetime(2026, 2, 3), 95.0, "%")
        ]
        result = TrendResult(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            data_points=data_points,
            direction="stable",
            change_percent=-5.0,
            period=TimePeriod.last_week(),
            granularity="daily"
        )
        
        # Act
        maximum = result.max_value
        
        # Assert
        assert maximum == 100.0
    
    def test_properties_with_empty_data_return_none(self):
        """Test that properties return None for empty data."""
        # Arrange
        result = TrendResult(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            data_points=[],
            direction="stable",
            change_percent=0.0,
            period=TimePeriod.today(),
            granularity="hourly"
        )
        
        # Act & Assert
        assert result.start_value is None
        assert result.end_value is None
        assert result.min_value is None
        assert result.max_value is None


class TestAnomalyResult:
    """Tests for AnomalyResult dataclass."""
    
    def test_creation_with_list_converts_to_tuple(self):
        """Test creating AnomalyResult converts anomalies list to tuple."""
        # Arrange
        anomalies = [
            Anomaly(
                timestamp=datetime(2026, 2, 8, 10, 0),
                metric=CanonicalMetric.ENERGY_TOTAL,
                expected_value=100.0,
                actual_value=150.0,
                deviation=3.5,
            )
        ]
        
        # Act
        result = AnomalyResult(
            is_anomalous=True,
            anomalies=anomalies,
            severity="high",
            asset_id="Line-1",
            metric=CanonicalMetric.ENERGY_TOTAL
        )
        
        # Assert
        assert isinstance(result.anomalies, tuple)
        assert len(result.anomalies) == 1
    
    def test_creation_with_no_anomalies_stores_empty_tuple(self):
        """Test creating AnomalyResult with no anomalies."""
        # Arrange & Act
        result = AnomalyResult(
            is_anomalous=False,
            anomalies=[],
            severity="none",
            asset_id="Line-1",
            metric=CanonicalMetric.OEE
        )
        
        # Assert
        assert result.is_anomalous is False
        assert len(result.anomalies) == 0
        assert result.severity == "none"
    
    def test_immutability_prevents_field_mutation(self):
        """Test that AnomalyResult is immutable."""
        # Arrange
        result = AnomalyResult(
            is_anomalous=True,
            anomalies=[],
            severity="low",
            asset_id="Line-1",
            metric=CanonicalMetric.OEE
        )
        
        # Act & Assert
        with pytest.raises((AttributeError, Exception)):
            result.severity = "high"
    
    def test_anomaly_count_property_returns_count(self):
        """Test anomaly_count property returns number of anomalies."""
        # Arrange
        anomalies = [
            Anomaly(
                timestamp=datetime.now(),
                metric=CanonicalMetric.PEAK_DEMAND,
                expected_value=80.0,
                actual_value=100.0,
                deviation=2.5,
            ),
            Anomaly(
                timestamp=datetime.now(),
                metric=CanonicalMetric.PEAK_DEMAND,
                expected_value=80.0,
                actual_value=110.0,
                deviation=3.0,
            )
        ]
        result = AnomalyResult(
            is_anomalous=True,
            anomalies=anomalies,
            severity="high",
            asset_id="Line-1",
            metric=CanonicalMetric.PEAK_DEMAND
        )
        
        # Act
        count = result.anomaly_count
        
        # Assert
        assert count == 2


class TestWhatIfResult:
    """Tests for WhatIfResult dataclass."""
    
    def test_creation_with_all_fields_creates_result(self):
        """Test creating WhatIfResult with all fields."""
        # Arrange
        scenario_name = "temperature_reduction"
        target_metric = CanonicalMetric.ENERGY_PER_UNIT
        baseline = 2.5
        projected = 2.2
        delta = -0.3
        delta_percent = -12.0
        confidence = 0.85
        factors = {"temperature": -5.0}
        
        # Act
        result = WhatIfResult(
            scenario_name=scenario_name,
            target_metric=target_metric,
            baseline=baseline,
            projected=projected,
            delta=delta,
            delta_percent=delta_percent,
            confidence=confidence,
            factors=factors,
            unit="kWh/unit"
        )
        
        # Assert
        assert result.scenario_name == scenario_name
        assert result.target_metric == target_metric
        assert result.baseline == baseline
        assert result.projected == projected
        assert result.delta == delta
        assert result.delta_percent == delta_percent
        assert result.confidence == confidence
        assert result.factors == factors
    
    def test_immutability_prevents_field_mutation(self):
        """Test that WhatIfResult is immutable."""
        # Arrange
        result = WhatIfResult(
            scenario_name="test",
            target_metric=CanonicalMetric.OEE,
            baseline=80.0,
            projected=85.0,
            delta=5.0,
            delta_percent=6.25,
            confidence=0.9,
            factors={"speed": 10.0}
        )
        
        # Act & Assert
        with pytest.raises((AttributeError, Exception)):
            result.confidence = 0.5
    
    def test_is_improvement_with_energy_metric_lower_is_better(self):
        """Test is_improvement for energy metric (lower is better)."""
        # Arrange
        result = WhatIfResult(
            scenario_name="reduce_energy",
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
            baseline=2.5,
            projected=2.2,
            delta=-0.3,
            delta_percent=-12.0,
            confidence=0.85,
            factors={"temp": -5.0}
        )
        
        # Act
        is_better = result.is_improvement
        
        # Assert
        assert is_better is True
    
    def test_is_improvement_with_oee_metric_higher_is_better(self):
        """Test is_improvement for OEE metric (higher is better)."""
        # Arrange
        result = WhatIfResult(
            scenario_name="improve_oee",
            target_metric=CanonicalMetric.OEE,
            baseline=80.0,
            projected=85.0,
            delta=5.0,
            delta_percent=6.25,
            confidence=0.9,
            factors={"maintenance": 1.0}
        )
        
        # Act
        is_better = result.is_improvement
        
        # Assert
        assert is_better is True
    
    def test_is_improvement_with_negative_delta_for_oee_is_false(self):
        """Test is_improvement with negative delta for OEE."""
        # Arrange
        result = WhatIfResult(
            scenario_name="worse_oee",
            target_metric=CanonicalMetric.OEE,
            baseline=85.0,
            projected=80.0,
            delta=-5.0,
            delta_percent=-5.88,
            confidence=0.8,
            factors={"speed": -10.0}
        )
        
        # Act
        is_better = result.is_improvement
        
        # Assert
        assert is_better is False
    
    def test_confidence_level_high_above_eighty_percent(self):
        """Test confidence_level property for high confidence."""
        # Arrange
        result = WhatIfResult(
            scenario_name="test",
            target_metric=CanonicalMetric.OEE,
            baseline=80.0,
            projected=85.0,
            delta=5.0,
            delta_percent=6.25,
            confidence=0.9,
            factors={}
        )
        
        # Act
        level = result.confidence_level
        
        # Assert
        assert level == "high"
    
    def test_confidence_level_medium_between_sixty_and_eighty(self):
        """Test confidence_level property for medium confidence."""
        # Arrange
        result = WhatIfResult(
            scenario_name="test",
            target_metric=CanonicalMetric.OEE,
            baseline=80.0,
            projected=85.0,
            delta=5.0,
            delta_percent=6.25,
            confidence=0.7,
            factors={}
        )
        
        # Act
        level = result.confidence_level
        
        # Assert
        assert level == "medium"
    
    def test_confidence_level_low_below_sixty_percent(self):
        """Test confidence_level property for low confidence."""
        # Arrange
        result = WhatIfResult(
            scenario_name="test",
            target_metric=CanonicalMetric.OEE,
            baseline=80.0,
            projected=85.0,
            delta=5.0,
            delta_percent=6.25,
            confidence=0.5,
            factors={}
        )
        
        # Act
        level = result.confidence_level
        
        # Assert
        assert level == "low"


# ══════════════════════════════════════════════════════════
# ConnectionTestResult
# ══════════════════════════════════════════════════════════


class TestConnectionTestResult:
    """Tests for ConnectionTestResult frozen dataclass."""

    def test_create_success_result_stores_all_fields(self) -> None:
        """ConnectionTestResult with success=True stores all fields."""
        # Arrange & Act
        result = ConnectionTestResult(
            success=True,
            latency_ms=42.5,
            message="Connected",
            adapter_name="RENERYO",
            resources_discovered=("Meter-1", "Meter-2"),
            api_version="1.0",
        )

        # Assert
        assert result.success is True
        assert result.latency_ms == 42.5
        assert result.message == "Connected"
        assert result.adapter_name == "RENERYO"
        assert result.resources_discovered == ("Meter-1", "Meter-2")
        assert result.api_version == "1.0"
        assert result.error_code == ""
        assert result.error_details == ""

    def test_create_failure_result_stores_error_fields(self) -> None:
        """ConnectionTestResult with error fields stores correctly."""
        # Arrange & Act
        result = ConnectionTestResult(
            success=False,
            latency_ms=100.0,
            message="Auth failed",
            adapter_name="RENERYO",
            error_code="RENERYO_AUTH_FAILED",
            error_details="HTTP 401",
        )

        # Assert
        assert result.success is False
        assert result.error_code == "RENERYO_AUTH_FAILED"
        assert result.error_details == "HTTP 401"

    def test_frozen_immutability_raises_on_attribute_set(self) -> None:
        """ConnectionTestResult is immutable (frozen=True)."""
        # Arrange
        result = ConnectionTestResult(
            success=True,
            latency_ms=1.0,
            message="OK",
            adapter_name="Mock",
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_resources_discovered_stored_as_tuple(self) -> None:
        """resources_discovered list input is converted to tuple."""
        # Arrange & Act
        result = ConnectionTestResult(
            success=True,
            latency_ms=1.0,
            message="OK",
            adapter_name="Mock",
            resources_discovered=["A", "B", "C"],
        )

        # Assert
        assert isinstance(result.resources_discovered, tuple)
        assert result.resources_discovered == ("A", "B", "C")

    def test_default_values_for_optional_fields(self) -> None:
        """Optional fields have correct defaults."""
        # Arrange & Act
        result = ConnectionTestResult(
            success=True,
            latency_ms=0.0,
            message="OK",
            adapter_name="Test",
        )

        # Assert
        assert result.resources_discovered == ()
        assert result.api_version == ""
        assert result.error_code == ""
        assert result.error_details == ""
