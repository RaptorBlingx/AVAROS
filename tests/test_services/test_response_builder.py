"""
ResponseBuilder Test Suite

Covers all public methods of ResponseBuilder:
    - Initialization (default verbosity, custom verbosity)
    - format_kpi_result (normal, brief, detailed; various metrics)
    - format_comparison_result (higher-better, lower-better, brief)
    - format_trend_result (up, down, stable, brief)
    - format_anomaly_result (anomalous, normal, brief)
    - format_whatif_result (improvement, degradation, brief, detailed)
    - Edge cases: zero values, large numbers
    - Helper methods: _format_value unit formatting

All tests use real domain result types imported from production code.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from skill.domain.models import (
    Anomaly,
    CanonicalMetric,
    DataPoint,
    TimePeriod,
)
from skill.domain.results import (
    AnomalyResult,
    ComparisonItem,
    ComparisonResult,
    KPIResult,
    TrendResult,
    WhatIfResult,
)
from skill.services.response_builder import ResponseBuilder


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def builder() -> ResponseBuilder:
    """ResponseBuilder with default (normal) verbosity."""
    return ResponseBuilder()


@pytest.fixture
def brief_builder() -> ResponseBuilder:
    """ResponseBuilder with brief verbosity."""
    return ResponseBuilder(verbosity="brief")


@pytest.fixture
def detailed_builder() -> ResponseBuilder:
    """ResponseBuilder with detailed verbosity."""
    return ResponseBuilder(verbosity="detailed")


@pytest.fixture
def period() -> TimePeriod:
    """A standard TimePeriod for test data."""
    return TimePeriod.today()


@pytest.fixture
def kpi_oee(period: TimePeriod) -> KPIResult:
    """OEE KPIResult at 82.5%."""
    return KPIResult(
        metric=CanonicalMetric.OEE,
        value=82.5,
        unit="%",
        asset_id="Line-1",
        period=period,
        timestamp=datetime.now(),
    )


@pytest.fixture
def kpi_energy(period: TimePeriod) -> KPIResult:
    """Energy per unit KPIResult."""
    return KPIResult(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        value=2.3,
        unit="kWh/unit",
        asset_id="Compressor-1",
        period=period,
        timestamp=datetime.now(),
    )


@pytest.fixture
def kpi_cycle_time(period: TimePeriod) -> KPIResult:
    """Cycle time KPIResult in seconds."""
    return KPIResult(
        metric=CanonicalMetric.CYCLE_TIME,
        value=45.8,
        unit="sec",
        asset_id="Line-1",
        period=period,
        timestamp=datetime.now(),
    )


@pytest.fixture
def comparison_energy(period: TimePeriod) -> ComparisonResult:
    """Energy comparison between two compressors."""
    return ComparisonResult(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        items=[
            ComparisonItem("Compressor-1", 2.3, 1),
            ComparisonItem("Compressor-2", 2.8, 2),
        ],
        winner_id="Compressor-1",
        difference=0.5,
        unit="kWh/unit",
        period=period,
    )


@pytest.fixture
def comparison_oee(period: TimePeriod) -> ComparisonResult:
    """OEE comparison (higher is better)."""
    return ComparisonResult(
        metric=CanonicalMetric.OEE,
        items=[
            ComparisonItem("Line-1", 85.0, 1),
            ComparisonItem("Line-2", 78.0, 2),
        ],
        winner_id="Line-1",
        difference=7.0,
        unit="%",
        period=period,
    )


@pytest.fixture
def trend_up(period: TimePeriod) -> TrendResult:
    """Upward trend for scrap rate."""
    now = datetime.now()
    return TrendResult(
        metric=CanonicalMetric.SCRAP_RATE,
        asset_id="Line-1",
        data_points=[
            DataPoint(timestamp=now, value=3.0, unit="%"),
            DataPoint(timestamp=now, value=3.5, unit="%"),
        ],
        direction="up",
        change_percent=12.5,
        period=period,
        granularity="daily",
    )


@pytest.fixture
def trend_down(period: TimePeriod) -> TrendResult:
    """Downward trend for energy."""
    now = datetime.now()
    return TrendResult(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="Line-1",
        data_points=[
            DataPoint(timestamp=now, value=2.8, unit="kWh"),
            DataPoint(timestamp=now, value=2.3, unit="kWh"),
        ],
        direction="down",
        change_percent=-8.0,
        period=period,
        granularity="daily",
    )


@pytest.fixture
def trend_stable(period: TimePeriod) -> TrendResult:
    """Stable trend for OEE."""
    now = datetime.now()
    return TrendResult(
        metric=CanonicalMetric.OEE,
        asset_id="Line-1",
        data_points=[
            DataPoint(timestamp=now, value=82.0, unit="%"),
            DataPoint(timestamp=now, value=82.1, unit="%"),
        ],
        direction="stable",
        change_percent=0.1,
        period=period,
        granularity="daily",
    )


@pytest.fixture
def anomaly_detected(period: TimePeriod) -> AnomalyResult:
    """Anomaly result with anomalies found."""
    now = datetime.now()
    return AnomalyResult(
        is_anomalous=True,
        anomalies=[
            Anomaly(
                timestamp=now,
                metric=CanonicalMetric.OEE,
                expected_value=82.0,
                actual_value=67.8,
                deviation=3.2,
                description="OEE dropped significantly below normal range",
            ),
            Anomaly(
                timestamp=now,
                metric=CanonicalMetric.OEE,
                expected_value=82.0,
                actual_value=65.0,
                deviation=3.8,
                description="Continued OEE degradation",
            ),
        ],
        severity="medium",
        asset_id="Line-1",
        metric=CanonicalMetric.OEE,
    )


@pytest.fixture
def anomaly_none() -> AnomalyResult:
    """Anomaly result with no anomalies."""
    return AnomalyResult(
        is_anomalous=False,
        anomalies=[],
        severity="none",
        asset_id="Line-1",
        metric=CanonicalMetric.OEE,
    )


@pytest.fixture
def whatif_improvement() -> WhatIfResult:
    """WhatIf result showing improvement (energy reduction)."""
    return WhatIfResult(
        scenario_name="temperature_reduction",
        target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        baseline=2.8,
        projected=2.2,
        delta=-0.6,
        delta_percent=-21.4,
        confidence=0.85,
        factors={"temperature": -5.0},
        unit="kWh/unit",
    )


@pytest.fixture
def whatif_degradation() -> WhatIfResult:
    """WhatIf result showing degradation (OEE decrease)."""
    return WhatIfResult(
        scenario_name="speed_increase",
        target_metric=CanonicalMetric.OEE,
        baseline=85.0,
        projected=78.0,
        delta=-7.0,
        delta_percent=-8.2,
        confidence=0.65,
        factors={"speed": 10.0},
        unit="%",
    )


# ══════════════════════════════════════════════════════════
# 1. Initialization
# ══════════════════════════════════════════════════════════


class TestResponseBuilderInit:
    """Tests for __init__()."""

    def test_init_default_verbosity_normal(self) -> None:
        """Default verbosity is 'normal'."""
        builder = ResponseBuilder()
        assert builder.verbosity == "normal"

    def test_init_custom_verbosity_brief(self) -> None:
        """Custom verbosity 'brief' is stored."""
        builder = ResponseBuilder(verbosity="brief")
        assert builder.verbosity == "brief"

    def test_init_custom_verbosity_detailed(self) -> None:
        """Custom verbosity 'detailed' is stored."""
        builder = ResponseBuilder(verbosity="detailed")
        assert builder.verbosity == "detailed"


# ══════════════════════════════════════════════════════════
# 2. format_kpi_result
# ══════════════════════════════════════════════════════════


class TestFormatKPIResult:
    """Tests for format_kpi_result()."""

    def test_format_kpi_result_oee_normal(
        self, builder: ResponseBuilder, kpi_oee: KPIResult
    ) -> None:
        """Normal verbosity includes metric name, asset, value."""
        result = builder.format_kpi_result(kpi_oee)
        assert "overall equipment effectiveness" in result.lower()
        assert "Line 1" in result
        assert "82.5 percent" in result

    def test_format_kpi_result_energy_normal(
        self, builder: ResponseBuilder, kpi_energy: KPIResult
    ) -> None:
        """Energy metric formats kWh correctly."""
        result = builder.format_kpi_result(kpi_energy)
        assert "energy per unit" in result.lower()
        assert "Compressor 1" in result
        assert "kilowatt hours" in result

    def test_format_kpi_result_cycle_time_seconds(
        self, builder: ResponseBuilder, kpi_cycle_time: KPIResult
    ) -> None:
        """Cycle time formats seconds correctly."""
        result = builder.format_kpi_result(kpi_cycle_time)
        assert "seconds" in result
        assert "45.8" in result

    def test_format_kpi_result_brief_value_only(
        self, brief_builder: ResponseBuilder, kpi_oee: KPIResult
    ) -> None:
        """Brief verbosity returns only the formatted value."""
        result = brief_builder.format_kpi_result(kpi_oee)
        assert "82.5 percent" in result
        # Brief should NOT include asset name or metric name
        assert "Line" not in result

    def test_format_kpi_result_detailed_includes_recommendation(
        self, detailed_builder: ResponseBuilder, period: TimePeriod
    ) -> None:
        """Detailed verbosity includes a recommendation when applicable."""
        # Low OEE triggers recommendation
        kpi_low_oee = KPIResult(
            metric=CanonicalMetric.OEE,
            value=65.0,
            unit="%",
            asset_id="Line-1",
            period=period,
            timestamp=datetime.now(),
        )
        result = detailed_builder.format_kpi_result(kpi_low_oee)
        assert "below industry average" in result.lower()

    def test_format_kpi_result_detailed_excellent_oee(
        self, detailed_builder: ResponseBuilder, period: TimePeriod
    ) -> None:
        """Detailed verbosity for high OEE gives positive recommendation."""
        kpi_high = KPIResult(
            metric=CanonicalMetric.OEE,
            value=90.0,
            unit="%",
            asset_id="Line-1",
            period=period,
            timestamp=datetime.now(),
        )
        result = detailed_builder.format_kpi_result(kpi_high)
        assert "excellent" in result.lower()

    def test_format_kpi_result_detailed_high_scrap(
        self, detailed_builder: ResponseBuilder, period: TimePeriod
    ) -> None:
        """Detailed verbosity for high scrap rate advises review."""
        kpi_scrap = KPIResult(
            metric=CanonicalMetric.SCRAP_RATE,
            value=7.5,
            unit="%",
            asset_id="Line-1",
            period=period,
            timestamp=datetime.now(),
        )
        result = detailed_builder.format_kpi_result(kpi_scrap)
        assert "high" in result.lower()

    def test_format_kpi_result_under_30_words(
        self, builder: ResponseBuilder, kpi_oee: KPIResult
    ) -> None:
        """Normal response stays under 30 words."""
        result = builder.format_kpi_result(kpi_oee)
        word_count = len(result.split())
        assert word_count <= 30, f"Response has {word_count} words: {result}"

    def test_format_kpi_result_zero_value(
        self, builder: ResponseBuilder, period: TimePeriod
    ) -> None:
        """Zero value formats without error."""
        kpi_zero = KPIResult(
            metric=CanonicalMetric.SCRAP_RATE,
            value=0.0,
            unit="%",
            asset_id="Line-1",
            period=period,
            timestamp=datetime.now(),
        )
        result = builder.format_kpi_result(kpi_zero)
        assert "0.0 percent" in result

    def test_format_kpi_result_large_value(
        self, builder: ResponseBuilder, period: TimePeriod
    ) -> None:
        """Very large value formats correctly."""
        kpi_large = KPIResult(
            metric=CanonicalMetric.ENERGY_TOTAL,
            value=99999.7,
            unit="kWh",
            asset_id="Plant-A",
            period=period,
            timestamp=datetime.now(),
        )
        result = builder.format_kpi_result(kpi_large)
        assert "99999.7" in result
        assert "kilowatt hours" in result


# ══════════════════════════════════════════════════════════
# 3. format_comparison_result
# ══════════════════════════════════════════════════════════


class TestFormatComparisonResult:
    """Tests for format_comparison_result()."""

    def test_format_comparison_energy_lower_better(
        self, builder: ResponseBuilder, comparison_energy: ComparisonResult
    ) -> None:
        """Energy comparison: lower is better → 'more efficient'."""
        result = builder.format_comparison_result(comparison_energy)
        assert "Compressor 1" in result
        assert "efficient" in result.lower()

    def test_format_comparison_oee_higher_better(
        self, builder: ResponseBuilder, comparison_oee: ComparisonResult
    ) -> None:
        """OEE comparison: higher is better → 'wins with better'."""
        result = builder.format_comparison_result(comparison_oee)
        assert "Line 1" in result
        assert "wins" in result.lower()

    def test_format_comparison_brief_winner_only(
        self, brief_builder: ResponseBuilder, comparison_energy: ComparisonResult
    ) -> None:
        """Brief verbosity shows winner and difference."""
        result = brief_builder.format_comparison_result(comparison_energy)
        assert "Compressor 1" in result
        assert "wins" in result.lower()

    def test_format_comparison_includes_difference(
        self, builder: ResponseBuilder, comparison_energy: ComparisonResult
    ) -> None:
        """Normal comparison includes the numeric difference."""
        result = builder.format_comparison_result(comparison_energy)
        # 0.5 kWh formatted as "0.5 kilowatt hours"
        assert "0.5" in result

    def test_format_comparison_under_30_words(
        self, builder: ResponseBuilder, comparison_energy: ComparisonResult
    ) -> None:
        """Response stays under 30 words."""
        result = builder.format_comparison_result(comparison_energy)
        word_count = len(result.split())
        assert word_count <= 30, f"Response has {word_count} words: {result}"


# ══════════════════════════════════════════════════════════
# 4. format_trend_result
# ══════════════════════════════════════════════════════════


class TestFormatTrendResult:
    """Tests for format_trend_result()."""

    def test_format_trend_up_includes_direction(
        self, builder: ResponseBuilder, trend_up: TrendResult
    ) -> None:
        """Upward trend mentions direction."""
        result = builder.format_trend_result(trend_up)
        assert "up" in result.lower()
        assert "12.5" in result

    def test_format_trend_down_includes_direction(
        self, builder: ResponseBuilder, trend_down: TrendResult
    ) -> None:
        """Downward trend mentions direction."""
        result = builder.format_trend_result(trend_down)
        assert "down" in result.lower()
        assert "8.0" in result

    def test_format_trend_stable_mentions_stable(
        self, builder: ResponseBuilder, trend_stable: TrendResult
    ) -> None:
        """Stable trend mentions stability."""
        result = builder.format_trend_result(trend_stable)
        assert "stable" in result.lower()

    def test_format_trend_brief_minimal(
        self, brief_builder: ResponseBuilder, trend_up: TrendResult
    ) -> None:
        """Brief verbosity gives minimal direction + change."""
        result = brief_builder.format_trend_result(trend_up)
        assert "up" in result.lower()
        assert "12.5" in result

    def test_format_trend_includes_metric_name(
        self, builder: ResponseBuilder, trend_up: TrendResult
    ) -> None:
        """Normal result includes the metric display name."""
        result = builder.format_trend_result(trend_up)
        assert "scrap rate" in result.lower()

    def test_format_trend_includes_period(
        self, builder: ResponseBuilder, trend_up: TrendResult
    ) -> None:
        """Normal result includes the period display name."""
        result = builder.format_trend_result(trend_up)
        assert "today" in result.lower()

    def test_format_trend_under_30_words(
        self, builder: ResponseBuilder, trend_up: TrendResult
    ) -> None:
        """Response stays under 30 words."""
        result = builder.format_trend_result(trend_up)
        word_count = len(result.split())
        assert word_count <= 30, f"Response has {word_count} words: {result}"


# ══════════════════════════════════════════════════════════
# 5. format_anomaly_result
# ══════════════════════════════════════════════════════════


class TestFormatAnomalyResult:
    """Tests for format_anomaly_result()."""

    def test_format_anomaly_detected_mentions_count(
        self, builder: ResponseBuilder, anomaly_detected: AnomalyResult
    ) -> None:
        """Detected anomalies show count and severity."""
        result = builder.format_anomaly_result(anomaly_detected)
        assert "2" in result
        assert "medium" in result.lower()

    def test_format_anomaly_none_reassuring(
        self, builder: ResponseBuilder, anomaly_none: AnomalyResult
    ) -> None:
        """No anomalies gives reassuring message."""
        result = builder.format_anomaly_result(anomaly_none)
        assert "no unusual" in result.lower() or "normal" in result.lower()

    def test_format_anomaly_brief_compact(
        self, brief_builder: ResponseBuilder, anomaly_detected: AnomalyResult
    ) -> None:
        """Brief verbosity is compact."""
        result = brief_builder.format_anomaly_result(anomaly_detected)
        assert "2" in result
        assert "medium" in result.lower()

    def test_format_anomaly_detailed_includes_description(
        self, detailed_builder: ResponseBuilder, anomaly_detected: AnomalyResult
    ) -> None:
        """Detailed verbosity includes first anomaly description."""
        result = detailed_builder.format_anomaly_result(anomaly_detected)
        assert "dropped" in result.lower() or "OEE" in result

    def test_format_anomaly_single_uses_singular(
        self, builder: ResponseBuilder
    ) -> None:
        """Single anomaly uses singular noun."""
        now = datetime.now()
        single = AnomalyResult(
            is_anomalous=True,
            anomalies=[
                Anomaly(
                    timestamp=now,
                    metric=CanonicalMetric.OEE,
                    expected_value=82.0,
                    actual_value=70.0,
                    deviation=2.5,
                ),
            ],
            severity="low",
            asset_id="Line-1",
            metric=CanonicalMetric.OEE,
        )
        result = builder.format_anomaly_result(single)
        assert "1 anomaly" in result
        assert "anomalies" not in result

    def test_format_anomaly_under_30_words(
        self, builder: ResponseBuilder, anomaly_detected: AnomalyResult
    ) -> None:
        """Response stays under 30 words."""
        result = builder.format_anomaly_result(anomaly_detected)
        word_count = len(result.split())
        assert word_count <= 30, f"Response has {word_count} words: {result}"


# ══════════════════════════════════════════════════════════
# 6. format_whatif_result
# ══════════════════════════════════════════════════════════


class TestFormatWhatIfResult:
    """Tests for format_whatif_result()."""

    def test_format_whatif_improvement_normal(
        self, builder: ResponseBuilder, whatif_improvement: WhatIfResult
    ) -> None:
        """Improvement scenario mentions savings/improvement."""
        result = builder.format_whatif_result(whatif_improvement)
        assert "energy per unit" in result.lower()
        assert "21.4" in result

    def test_format_whatif_includes_baseline_and_projected(
        self, builder: ResponseBuilder, whatif_improvement: WhatIfResult
    ) -> None:
        """Normal result includes baseline and projected values."""
        result = builder.format_whatif_result(whatif_improvement)
        assert "2.8" in result
        assert "2.2" in result

    def test_format_whatif_brief_pct_only(
        self, brief_builder: ResponseBuilder, whatif_improvement: WhatIfResult
    ) -> None:
        """Brief verbosity gives percentage and change word."""
        result = brief_builder.format_whatif_result(whatif_improvement)
        assert "21.4" in result

    def test_format_whatif_detailed_includes_confidence(
        self, detailed_builder: ResponseBuilder, whatif_improvement: WhatIfResult
    ) -> None:
        """Detailed includes confidence level."""
        result = detailed_builder.format_whatif_result(whatif_improvement)
        assert "high" in result.lower() or "85" in result

    def test_format_whatif_degradation_normal(
        self, builder: ResponseBuilder, whatif_degradation: WhatIfResult
    ) -> None:
        """Degradation scenario mentions decrease/increase."""
        result = builder.format_whatif_result(whatif_degradation)
        # OEE going down is NOT an improvement
        assert "8.2" in result

    def test_format_whatif_under_30_words_normal(
        self, builder: ResponseBuilder, whatif_improvement: WhatIfResult
    ) -> None:
        """Normal response stays under 30 words."""
        result = builder.format_whatif_result(whatif_improvement)
        word_count = len(result.split())
        assert word_count <= 30, f"Response has {word_count} words: {result}"

    def test_format_whatif_zero_delta(
        self, builder: ResponseBuilder
    ) -> None:
        """WhatIf with zero change still formats."""
        result_obj = WhatIfResult(
            scenario_name="no_change",
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
            baseline=2.5,
            projected=2.5,
            delta=0.0,
            delta_percent=0.0,
            confidence=0.9,
            factors={"temperature": 0},
            unit="kWh/unit",
        )
        result = builder.format_whatif_result(result_obj)
        assert isinstance(result, str)
        assert "0.0" in result


# ══════════════════════════════════════════════════════════
# 7. Helper Methods — _format_value
# ══════════════════════════════════════════════════════════


class TestFormatValue:
    """Tests for _format_value() via public methods."""

    def test_format_value_percent(self, builder: ResponseBuilder) -> None:
        """Percent unit → 'X.X percent'."""
        result = builder._format_value(82.5, "%")
        assert result == "82.5 percent"

    def test_format_value_kwh(self, builder: ResponseBuilder) -> None:
        """kWh unit → 'X.X kilowatt hours'."""
        result = builder._format_value(2.3, "kWh")
        assert result == "2.3 kilowatt hours"

    def test_format_value_kg(self, builder: ResponseBuilder) -> None:
        """kg unit → 'X.X kilograms'."""
        result = builder._format_value(15.0, "kg CO₂-eq")
        assert result == "15.0 kilograms"

    def test_format_value_celsius(self, builder: ResponseBuilder) -> None:
        """°C unit → 'X.X degrees celsius'."""
        result = builder._format_value(25.3, "°C")
        assert result == "25.3 degrees celsius"

    def test_format_value_seconds(self, builder: ResponseBuilder) -> None:
        """sec unit → 'X.X seconds'."""
        result = builder._format_value(45.8, "sec")
        assert result == "45.8 seconds"

    def test_format_value_minutes(self, builder: ResponseBuilder) -> None:
        """min unit → 'X.X minutes'."""
        result = builder._format_value(12.0, "min")
        assert result == "12.0 minutes"

    def test_format_value_days(self, builder: ResponseBuilder) -> None:
        """days unit → 'X.X days'."""
        result = builder._format_value(5.0, "days")
        assert result == "5.0 days"

    def test_format_value_unknown_unit_lowercase(
        self, builder: ResponseBuilder
    ) -> None:
        """Unknown unit is lowercased."""
        result = builder._format_value(42.0, "UNITS/HR")
        assert result == "42.0 units/hr"


# ══════════════════════════════════════════════════════════
# 8. _format_asset_name
# ══════════════════════════════════════════════════════════


class TestFormatAssetName:
    """Tests for _format_asset_name()."""

    def test_format_asset_name_hyphen_to_space(
        self, builder: ResponseBuilder
    ) -> None:
        """Hyphens are replaced with spaces."""
        assert builder._format_asset_name("Line-1") == "Line 1"

    def test_format_asset_name_underscore_to_space(
        self, builder: ResponseBuilder
    ) -> None:
        """Underscores are replaced with spaces."""
        assert builder._format_asset_name("Compressor_2") == "Compressor 2"

    def test_format_asset_name_no_separator(
        self, builder: ResponseBuilder
    ) -> None:
        """Name without separators is unchanged."""
        assert builder._format_asset_name("PlantA") == "PlantA"


# ══════════════════════════════════════════════════════════
# 9. _is_lower_better
# ══════════════════════════════════════════════════════════


class TestIsLowerBetter:
    """Tests for _is_lower_better()."""

    @pytest.mark.parametrize(
        "metric",
        [
            CanonicalMetric.ENERGY_PER_UNIT,
            CanonicalMetric.SCRAP_RATE,
            CanonicalMetric.CO2_PER_UNIT,
            CanonicalMetric.CYCLE_TIME,
            CanonicalMetric.SUPPLIER_LEAD_TIME,
        ],
    )
    def test_lower_is_better_for_cost_metrics(
        self, builder: ResponseBuilder, metric: CanonicalMetric
    ) -> None:
        """Cost/waste metrics: lower is better."""
        assert builder._is_lower_better(metric) is True

    @pytest.mark.parametrize(
        "metric",
        [
            CanonicalMetric.OEE,
            CanonicalMetric.MATERIAL_EFFICIENCY,
            CanonicalMetric.THROUGHPUT,
            CanonicalMetric.SUPPLIER_ON_TIME,
            CanonicalMetric.RECYCLED_CONTENT,
        ],
    )
    def test_higher_is_better_for_performance_metrics(
        self, builder: ResponseBuilder, metric: CanonicalMetric
    ) -> None:
        """Performance metrics: higher is better."""
        assert builder._is_lower_better(metric) is False
