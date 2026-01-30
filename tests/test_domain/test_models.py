"""
Domain Model Unit Tests

Tests for canonical manufacturing data models.
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
    
    def test_all_metrics_have_default_unit(self):
        """Every metric should have a default unit."""
        for metric in CanonicalMetric:
            assert metric.default_unit is not None
            assert len(metric.default_unit) > 0 or metric.default_unit == ""
    
    def test_all_metrics_have_display_name(self):
        """Every metric should have a human-readable display name."""
        for metric in CanonicalMetric:
            assert metric.display_name is not None
            assert len(metric.display_name) > 0
    
    def test_from_string_exact_match(self):
        """Should match exact enum values."""
        assert CanonicalMetric.from_string("oee") == CanonicalMetric.OEE
        assert CanonicalMetric.from_string("energy_per_unit") == CanonicalMetric.ENERGY_PER_UNIT
    
    def test_from_string_aliases(self):
        """Should match common aliases."""
        assert CanonicalMetric.from_string("energy") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string("power") == CanonicalMetric.ENERGY_PER_UNIT
        assert CanonicalMetric.from_string("scrap") == CanonicalMetric.SCRAP_RATE
    
    def test_from_string_case_insensitive(self):
        """Should be case-insensitive."""
        assert CanonicalMetric.from_string("OEE") == CanonicalMetric.OEE
        assert CanonicalMetric.from_string("Energy_Per_Unit") == CanonicalMetric.ENERGY_PER_UNIT
    
    def test_from_string_unknown_raises(self):
        """Should raise ValueError for unknown metrics."""
        with pytest.raises(ValueError):
            CanonicalMetric.from_string("unknown_metric")


class TestTimePeriod:
    """Tests for TimePeriod value object."""
    
    def test_today_period(self):
        """today() should return current day period."""
        period = TimePeriod.today()
        assert period.display_name == "today"
        assert period.start.date() == datetime.now().date()
    
    def test_this_week_period(self):
        """this_week() should start from Monday."""
        period = TimePeriod.this_week()
        assert period.display_name == "this week"
        assert period.start.weekday() == 0  # Monday
    
    def test_last_week_period(self):
        """last_week() should be 7 days before this week."""
        period = TimePeriod.last_week()
        assert period.display_name == "last week"
        assert period.duration_days == 7
    
    def test_from_natural_language(self):
        """Should parse natural language periods."""
        assert TimePeriod.from_natural_language("today").display_name == "today"
        assert TimePeriod.from_natural_language("last week").display_name == "last week"
    
    def test_invalid_period_raises(self):
        """Should raise for end before start."""
        with pytest.raises(ValueError):
            TimePeriod(
                start=datetime.now(),
                end=datetime.now() - timedelta(days=1),
            )
    
    def test_immutability(self):
        """TimePeriod should be immutable."""
        period = TimePeriod.today()
        with pytest.raises(AttributeError):
            period.start = datetime.now()


class TestDataPoint:
    """Tests for DataPoint value object."""
    
    def test_to_dict(self):
        """Should serialize to dictionary."""
        dp = DataPoint(
            timestamp=datetime(2026, 1, 30, 12, 0),
            value=42.5,
            unit="%",
        )
        result = dp.to_dict()
        assert result["value"] == 42.5
        assert result["unit"] == "%"
        assert "timestamp" in result


class TestScenarioParameter:
    """Tests for ScenarioParameter."""
    
    def test_delta_calculation(self):
        """Should calculate delta correctly."""
        param = ScenarioParameter("temp", 25.0, 20.0, "°C")
        assert param.delta == -5.0
    
    def test_delta_percent_calculation(self):
        """Should calculate percentage change."""
        param = ScenarioParameter("temp", 100.0, 80.0, "°C")
        assert param.delta_percent == -20.0
    
    def test_delta_percent_zero_baseline(self):
        """Should handle zero baseline."""
        param = ScenarioParameter("temp", 0.0, 10.0, "°C")
        assert param.delta_percent == 0.0


class TestWhatIfScenario:
    """Tests for WhatIfScenario."""
    
    def test_immutability(self):
        """Scenario should be immutable."""
        scenario = WhatIfScenario(
            name="test",
            asset_id="Line-1",
            parameters=[ScenarioParameter("temp", 25.0, 20.0, "°C")],
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )
        with pytest.raises(AttributeError):
            scenario.name = "changed"
    
    def test_parameters_are_tuple(self):
        """Parameters should be stored as tuple."""
        scenario = WhatIfScenario(
            name="test",
            asset_id="Line-1",
            parameters=[ScenarioParameter("temp", 25.0, 20.0, "°C")],
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )
        assert isinstance(scenario.parameters, tuple)


class TestAnomaly:
    """Tests for Anomaly model."""
    
    def test_severity_low(self):
        """Deviation < 2 should be low severity."""
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.OEE,
            expected_value=80.0,
            actual_value=78.0,
            deviation=1.5,
        )
        assert anomaly.severity == "low"
    
    def test_severity_critical(self):
        """Deviation >= 4 should be critical severity."""
        anomaly = Anomaly(
            timestamp=datetime.now(),
            metric=CanonicalMetric.OEE,
            expected_value=80.0,
            actual_value=50.0,
            deviation=4.5,
        )
        assert anomaly.severity == "critical"
