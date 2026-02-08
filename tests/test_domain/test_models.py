"""
Domain Model Unit Tests

Tests for canonical manufacturing data models.
Comprehensive coverage for CanonicalMetric, TimePeriod, DataPoint, 
ScenarioParameter, WhatIfScenario, and Anomaly.
"""

import pytest
from datetime import datetime, timedelta

from skill.domain.models import (
    CanonicalMetric,
    TimePeriod,
    DataPoint,
    WhatIfScenario,
    ScenarioParameter,
    Anomaly,
)


class TestCanonicalMetric:
    """Tests for CanonicalMetric enum."""
    
    def test_all_19_metrics_are_defined(self):
        """Should have exactly 19 canonical metrics."""
        # Arrange & Act
        metrics = list(CanonicalMetric)
        
        # Assert
        assert len(metrics) == 19
    
    def test_all_metrics_have_default_unit(self):
        """Every metric should have a default unit."""
        # Arrange & Act & Assert
        for metric in CanonicalMetric:
            assert metric.default_unit is not None
            assert isinstance(metric.default_unit, str)
    
    def test_all_metrics_have_display_name(self):
        """Every metric should have a human-readable display name."""
        # Arrange & Act & Assert
        for metric in CanonicalMetric:
            assert metric.display_name is not None
            assert len(metric.display_name) > 0
    
    def test_from_string_with_exact_match_returns_metric(self):
        """Should match exact enum values."""
        # Arrange & Act & Assert
        assert CanonicalMetric.from_string("oee") == CanonicalMetric.OEE
        assert CanonicalMetric.from_string("energy_per_unit") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string("scrap_rate") == CanonicalMetric.SCRAP_RATE
    
    def test_from_string_with_aliases_returns_metric(self):
        """Should match common aliases."""
        # Arrange & Act & Assert
        assert CanonicalMetric.from_string("energy") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string("power") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string("electricity") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string("scrap") == CanonicalMetric.SCRAP_RATE
        assert CanonicalMetric.from_string("waste") == CanonicalMetric.SCRAP_RATE
        assert CanonicalMetric.from_string("carbon") == CanonicalMetric.CO2_PER_UNIT
        assert CanonicalMetric.from_string("co2") == CanonicalMetric.CO2_PER_UNIT
        assert CanonicalMetric.from_string("emissions") == CanonicalMetric.CO2_PER_UNIT
    
    def test_from_string_case_insensitive_returns_metric(self):
        """Should be case-insensitive."""
        # Arrange & Act & Assert
        assert CanonicalMetric.from_string("OEE") == CanonicalMetric.OEE
        assert CanonicalMetric.from_string("Energy_Per_Unit") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string("SCRAP_RATE") == CanonicalMetric.SCRAP_RATE
    
    def test_from_string_with_spaces_returns_metric(self):
        """Should handle spaces in input."""
        # Arrange & Act & Assert
        assert CanonicalMetric.from_string("energy per unit") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string(" oee ") == CanonicalMetric.OEE
    
    def test_from_string_with_hyphens_returns_metric(self):
        """Should handle hyphens in input."""
        # Arrange & Act & Assert
        assert CanonicalMetric.from_string("energy-per-unit") == CanonicalMetric.ENERGY_PER_UNIT
    
    def test_from_string_with_unknown_metric_raises_valueerror(self):
        """Should raise ValueError for unknown metrics."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Unknown metric"):
            CanonicalMetric.from_string("unknown_metric")
    
    def test_display_name_returns_readable_name(self):
        """Display name should be human-readable."""
        # Arrange & Act & Assert
        assert CanonicalMetric.OEE.display_name == "overall equipment effectiveness"
        assert CanonicalMetric.ENERGY_PER_UNIT.display_name == "energy per unit"
        assert CanonicalMetric.SCRAP_RATE.display_name == "scrap rate"
        assert CanonicalMetric.CO2_TOTAL.display_name == "total carbon emissions"
    
    def test_default_unit_returns_correct_unit(self):
        """Default unit should match metric type."""
        # Arrange & Act & Assert
        assert CanonicalMetric.ENERGY_PER_UNIT.default_unit == "kWh/unit"
        assert CanonicalMetric.OEE.default_unit == "%"
        assert CanonicalMetric.THROUGHPUT.default_unit == "units/hr"
        assert CanonicalMetric.CYCLE_TIME.default_unit == "sec"
        assert CanonicalMetric.CO2_TOTAL.default_unit == "kg CO₂-eq"


class TestTimePeriod:
    """Tests for TimePeriod value object."""
    
    def test_today_period_returns_current_day(self):
        """today() should return current day period."""
        # Arrange & Act
        period = TimePeriod.today()
        
        # Assert
        assert period.display_name == "today"
        assert period.start.date() == datetime.now().date()
        assert period.start.hour == 0
        assert period.start.minute == 0
    
    def test_this_week_period_starts_on_monday(self):
        """this_week() should start from Monday."""
        # Arrange & Act
        period = TimePeriod.this_week()
        
        # Assert
        assert period.display_name == "this week"
        assert period.start.weekday() == 0  # Monday
    
    def test_last_week_period_is_seven_days(self):
        """last_week() should be 7 days before this week."""
        # Arrange & Act
        period = TimePeriod.last_week()
        
        # Assert
        assert period.display_name == "last week"
        assert period.duration_days == 7
    
    def test_last_month_period_is_thirty_days(self):
        """last_month() should cover 30 days."""
        # Arrange & Act
        period = TimePeriod.last_month()
        
        # Assert
        assert period.display_name == "last month"
        assert 29.5 <= period.duration_days <= 30.5  # Allow for time precision
    
    def test_from_natural_language_with_today_returns_today(self):
        """Should parse 'today' correctly."""
        # Arrange & Act
        period = TimePeriod.from_natural_language("today")
        
        # Assert
        assert period.display_name == "today"
    
    def test_from_natural_language_with_last_week_returns_last_week(self):
        """Should parse 'last week' correctly."""
        # Arrange & Act
        period = TimePeriod.from_natural_language("last week")
        
        # Assert
        assert period.display_name == "last week"
    
    def test_from_natural_language_with_past_week_returns_last_week(self):
        """Should parse 'past week' as last week."""
        # Arrange & Act
        period = TimePeriod.from_natural_language("past week")
        
        # Assert
        assert period.display_name == "last week"
    
    def test_from_natural_language_case_insensitive(self):
        """Should handle mixed case input."""
        # Arrange & Act
        period = TimePeriod.from_natural_language("TODAY")
        
        # Assert
        assert period.display_name == "today"
    
    def test_creation_with_end_before_start_raises_valueerror(self):
        """Should raise ValueError for invalid period."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError):
            TimePeriod(
                start=datetime.now(),
                end=datetime.now() - timedelta(days=1),
            )
    
    def test_immutability_prevents_field_modification(self):
        """TimePeriod should be immutable."""
        # Arrange
        period = TimePeriod.today()
        
        # Act & Assert
        with pytest.raises(AttributeError):
            period.start = datetime.now()
    
    def test_duration_days_calculates_correctly(self):
        """duration_days should return accurate day count."""
        # Arrange
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 8, 12, 0, 0)
        period = TimePeriod(start=start, end=end, display_name="test")
        
        # Act
        duration = period.duration_days
        
        # Assert
        assert duration == 7.5
    
    def test_custom_period_creation_with_display_name(self):
        """Should create custom period with all fields."""
        # Arrange
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        
        # Act
        period = TimePeriod(start=start, end=end, display_name="January 2026")
        
        # Assert
        assert period.start == start
        assert period.end == end
        assert period.display_name == "January 2026"


class TestDataPoint:
    """Tests for DataPoint value object."""
    
    def test_creation_with_all_fields_creates_datapoint(self):
        """Should create DataPoint with all fields."""
        # Arrange
        timestamp = datetime(2026, 1, 30, 12, 0)
        value = 42.5
        unit = "%"
        
        # Act
        dp = DataPoint(timestamp=timestamp, value=value, unit=unit)
        
        # Assert
        assert dp.timestamp == timestamp
        assert dp.value == value
        assert dp.unit == unit
    
    def test_creation_without_unit_uses_empty_string(self):
        """Should use empty string for unit if not provided."""
        # Arrange & Act
        dp = DataPoint(timestamp=datetime.now(), value=100.0)
        
        # Assert
        assert dp.unit == ""
    
    def test_to_dict_serializes_all_fields(self):
        """Should serialize to dictionary."""
        # Arrange
        timestamp = datetime(2026, 1, 30, 12, 0)
        dp = DataPoint(timestamp=timestamp, value=42.5, unit="%")
        
        # Act
        result = dp.to_dict()
        
        # Assert
        assert result["value"] == 42.5
        assert result["unit"] == "%"
        assert "timestamp" in result
        assert timestamp.isoformat() in result["timestamp"]
    
    def test_immutability_prevents_field_modification(self):
        """DataPoint should be immutable."""
        # Arrange
        dp = DataPoint(timestamp=datetime.now(), value=50.0, unit="%")
        
        # Act & Assert
        with pytest.raises(AttributeError):
            dp.value = 100.0


class TestScenarioParameter:
    """Tests for ScenarioParameter."""
    
    def test_delta_calculates_difference_correctly(self):
        """Should calculate delta correctly."""
        # Arrange
        param = ScenarioParameter("temp", 25.0, 20.0, "°C")
        
        # Act & Assert
        assert param.delta == -5.0
    
    def test_delta_with_positive_change_is_positive(self):
        """Should return positive delta for increase."""
        # Arrange
        param = ScenarioParameter("speed", 100.0, 120.0, "rpm")
        
        # Act & Assert
        assert param.delta == 20.0
    
    def test_delta_percent_calculates_percentage_change(self):
        """Should calculate percentage change."""
        # Arrange
        param = ScenarioParameter("temp", 100.0, 80.0, "°C")
        
        # Act & Assert
        assert param.delta_percent == -20.0
    
    def test_delta_percent_with_zero_baseline_returns_zero(self):
        """Should handle zero baseline."""
        # Arrange
        param = ScenarioParameter("temp", 0.0, 10.0, "°C")
        
        # Act & Assert
        assert param.delta_percent == 0.0
    
    def test_delta_percent_with_negative_values(self):
        """Should handle negative values correctly."""
        # Arrange
        param = ScenarioParameter("loss", -10.0, -5.0, "units")
        
        # Act & Assert
        assert param.delta == 5.0
        assert param.delta_percent == -50.0
    
    def test_immutability_prevents_field_modification(self):
        """ScenarioParameter should be immutable."""
        # Arrange
        param = ScenarioParameter("test", 10.0, 20.0, "unit")
        
        # Act & Assert
        with pytest.raises(AttributeError):
            param.baseline_value = 15.0


class TestWhatIfScenario:
    """Tests for WhatIfScenario."""
    
    def test_creation_with_list_converts_to_tuple(self):
        """Should convert parameters list to tuple."""
        # Arrange
        params = [ScenarioParameter("temp", 25.0, 20.0, "°C")]
        
        # Act
        scenario = WhatIfScenario(
            name="test",
            asset_id="Line-1",
            parameters=params,
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )
        
        # Assert
        assert isinstance(scenario.parameters, tuple)
    
    def test_creation_with_tuple_stores_tuple(self):
        """Parameters should be stored as tuple."""
        # Arrange
        params = (ScenarioParameter("temp", 25.0, 20.0, "°C"),)
        
        # Act
        scenario = WhatIfScenario(
            name="test",
            asset_id="Line-1",
            parameters=params,
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )
        
        # Assert
        assert scenario.parameters == params
    
    def test_creation_with_multiple_parameters(self):
        """Should handle multiple parameters."""
        # Arrange
        params = [
            ScenarioParameter("temp", 25.0, 20.0, "°C"),
            ScenarioParameter("speed", 100.0, 110.0, "rpm"),
            ScenarioParameter("pressure", 5.0, 4.5, "bar"),
        ]
        
        # Act
        scenario = WhatIfScenario(
            name="multi_param_test",
            asset_id="Machine-5",
            parameters=params,
            target_metric=CanonicalMetric.THROUGHPUT,
        )
        
        # Assert
        assert len(scenario.parameters) == 3
        assert scenario.parameters[0].name == "temp"
        assert scenario.parameters[1].name == "speed"
        assert scenario.parameters[2].name == "pressure"
    
    def test_immutability_prevents_name_modification(self):
        """Scenario should be immutable."""
        # Arrange
        scenario = WhatIfScenario(
            name="test",
            asset_id="Line-1",
            parameters=[ScenarioParameter("temp", 25.0, 20.0, "°C")],
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )
        
        # Act & Assert
        with pytest.raises(AttributeError):
            scenario.name = "changed"
    
    def test_all_fields_accessible(self):
        """All scenario fields should be accessible."""
        # Arrange
        params = [ScenarioParameter("temp", 25.0, 20.0, "°C")]
        
        # Act
        scenario = WhatIfScenario(
            name="efficiency_test",
            asset_id="Compressor-3",
            parameters=params,
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )
        
        # Assert
        assert scenario.name == "efficiency_test"
        assert scenario.asset_id == "Compressor-3"
        assert len(scenario.parameters) == 1
        assert scenario.target_metric == CanonicalMetric.ENERGY_PER_UNIT


class TestAnomaly:
    """Tests for Anomaly model."""
    
    def test_severity_low_for_small_deviation(self):
        """Deviation < 2 should be low severity."""
        # Arrange
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.OEE,
            expected_value=80.0,
            actual_value=78.0,
            deviation=1.5,
        )
        
        # Act & Assert
        assert anomaly.severity == "low"
    
    def test_severity_medium_for_moderate_deviation(self):
        """Deviation 2-3 should be medium severity."""
        # Arrange
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.OEE,
            expected_value=80.0,
            actual_value=75.0,
            deviation=2.5,
        )
        
        # Act & Assert
        assert anomaly.severity == "medium"
    
    def test_severity_high_for_large_deviation(self):
        """Deviation 3-4 should be high severity."""
        # Arrange
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.ENERGY_TOTAL,
            expected_value=100.0,
            actual_value=130.0,
            deviation=3.5,
        )
        
        # Act & Assert
        assert anomaly.severity == "high"
    
    def test_severity_critical_for_extreme_deviation(self):
        """Deviation >= 4 should be critical severity."""
        # Arrange
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.OEE,
            expected_value=80.0,
            actual_value=50.0,
            deviation=4.5,
        )
        
        # Act & Assert
        assert anomaly.severity == "critical"
    
    def test_severity_with_negative_deviation(self):
        """Should handle negative deviations correctly."""
        # Arrange
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.SCRAP_RATE,
            expected_value=5.0,
            actual_value=2.0,
            deviation=-2.5,
        )
        
        # Act & Assert
        assert anomaly.severity == "medium"
    
    def test_creation_with_description(self):
        """Should store description if provided."""
        # Arrange
        description = "Unexpected spike in energy consumption"
        
        # Act
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.ENERGY_TOTAL,
            expected_value=100.0,
            actual_value=150.0,
            deviation=3.0,
            description=description,
        )
        
        # Assert
        assert anomaly.description == description
    
    def test_creation_without_description_uses_empty_string(self):
        """Should use empty string for description if not provided."""
        # Arrange & Act
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.OEE,
            expected_value=80.0,
            actual_value=70.0,
            deviation=2.0,
        )
        
        # Assert
        assert anomaly.description == ""
    
    def test_immutability_prevents_field_modification(self):
        """Anomaly should be immutable."""
        # Arrange
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.OEE,
            expected_value=80.0,
            actual_value=70.0,
            deviation=2.0,
        )
        
        # Act & Assert
        with pytest.raises(AttributeError):
            anomaly.expected_value = 85.0
    
    def test_all_fields_accessible(self):
        """All anomaly fields should be accessible."""
        # Arrange
        timestamp = datetime(2026, 2, 8, 14, 30)
        
        # Act
        anomaly = Anomaly(
            timestamp=timestamp,
            metric=CanonicalMetric.THROUGHPUT,
            expected_value=50.0,
            actual_value=35.0,
            deviation=-3.5,
            description="Production slowdown detected"
        )
        
        # Assert
        assert anomaly.timestamp == timestamp
        assert anomaly.metric == CanonicalMetric.THROUGHPUT
        assert anomaly.expected_value == 50.0
        assert anomaly.actual_value == 35.0
        assert anomaly.deviation == -3.5
        assert "slowdown" in anomaly.description.lower()

