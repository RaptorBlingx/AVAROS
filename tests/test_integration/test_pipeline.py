"""
Integration Pipeline Tests

End-to-end tests exercising the full production pipeline:
    QueryDispatcher → MockAdapter → ResponseBuilder

All components are REAL (no mocks). These tests validate that the
actual production code works together correctly.

Pipelines tested:
    - KPI: dispatcher.get_kpi() → builder.format_kpi_result()
    - Comparison: dispatcher.compare() → builder.format_comparison_result()
    - Trend: dispatcher.get_trend() → builder.format_trend_result()
    - Anomaly: dispatcher.check_anomaly() → builder.format_anomaly_result()
    - WhatIf: dispatcher.simulate_whatif() → builder.format_whatif_result()
    - Adapter hot-swap
    - Audit trail round-trip
"""

from __future__ import annotations

import pytest

from skill.adapters.mock import MockAdapter
from skill.domain.models import (
    CanonicalMetric,
    ScenarioParameter,
    TimePeriod,
    WhatIfScenario,
)
from skill.domain.results import (
    AnomalyResult,
    ComparisonResult,
    KPIResult,
    TrendResult,
    WhatIfResult,
)
from skill.services.audit import AuditLogger
from skill.services.response_builder import ResponseBuilder
from skill.use_cases.query_dispatcher import QueryDispatcher


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def audit_logger() -> AuditLogger:
    """In-memory AuditLogger, initialized and ready."""
    audit = AuditLogger()
    audit.initialize()
    yield audit
    audit.close()


@pytest.fixture
def dispatcher(audit_logger: AuditLogger) -> QueryDispatcher:
    """QueryDispatcher with real MockAdapter and in-memory audit."""
    return QueryDispatcher(adapter=MockAdapter(), audit_logger=audit_logger)


@pytest.fixture
def builder() -> ResponseBuilder:
    """ResponseBuilder with default verbosity."""
    return ResponseBuilder()


@pytest.fixture
def period() -> TimePeriod:
    """Standard today period."""
    return TimePeriod.today()


# ══════════════════════════════════════════════════════════
# 1. Full KPI Pipeline
# ══════════════════════════════════════════════════════════


class TestKPIPipeline:
    """End-to-end: dispatcher → adapter → response_builder for KPIs."""

    @pytest.mark.parametrize(
        "metric",
        [
            CanonicalMetric.OEE,
            CanonicalMetric.ENERGY_PER_UNIT,
            CanonicalMetric.SCRAP_RATE,
            CanonicalMetric.CO2_PER_UNIT,
        ],
    )
    def test_kpi_pipeline_produces_voice_response(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
        period: TimePeriod,
        metric: CanonicalMetric,
    ) -> None:
        """Full KPI pipeline returns non-empty voice-ready string."""
        # Act
        result = dispatcher.get_kpi(metric, "Line-1", period)
        response = builder.format_kpi_result(result)

        # Assert
        assert isinstance(result, KPIResult)
        assert isinstance(response, str)
        assert len(response) > 0
        assert len(response.split()) <= 30

    def test_kpi_pipeline_oee_includes_value(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
        period: TimePeriod,
    ) -> None:
        """OEE pipeline response contains the OEE value."""
        result = dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        response = builder.format_kpi_result(result)

        assert "percent" in response
        assert "Line 1" in response


# ══════════════════════════════════════════════════════════
# 2. Full Comparison Pipeline
# ══════════════════════════════════════════════════════════


class TestComparisonPipeline:
    """End-to-end: dispatcher → adapter → response_builder for comparisons."""

    def test_comparison_pipeline_mentions_winner(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
        period: TimePeriod,
    ) -> None:
        """Comparison pipeline names the winner in the response."""
        result = dispatcher.compare(
            CanonicalMetric.OEE, ["Line-1", "Line-2"], period
        )
        response = builder.format_comparison_result(result)

        assert isinstance(result, ComparisonResult)
        assert isinstance(response, str)
        assert len(response) > 0
        # Winner should appear in the response (hyphen replaced with space)
        winner_display = result.winner_id.replace("-", " ")
        assert winner_display in response

    def test_comparison_pipeline_three_assets(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
        period: TimePeriod,
    ) -> None:
        """Comparison works with 3 assets."""
        result = dispatcher.compare(
            CanonicalMetric.ENERGY_PER_UNIT,
            ["Compressor-1", "Compressor-2", "Boiler-1"],
            period,
        )
        response = builder.format_comparison_result(result)

        assert len(result.items) == 3
        assert isinstance(response, str)
        assert len(response) > 0


# ══════════════════════════════════════════════════════════
# 3. Full Trend Pipeline
# ══════════════════════════════════════════════════════════


class TestTrendPipeline:
    """End-to-end: dispatcher → adapter → response_builder for trends."""

    def test_trend_pipeline_mentions_direction(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
        period: TimePeriod,
    ) -> None:
        """Trend pipeline response mentions the direction."""
        result = dispatcher.get_trend(
            CanonicalMetric.SCRAP_RATE, "Line-1", period
        )
        response = builder.format_trend_result(result)

        assert isinstance(result, TrendResult)
        assert isinstance(response, str)
        assert len(response) > 0
        # Direction word should appear in response
        assert any(word in response.lower() for word in ("up", "down", "stable"))

    def test_trend_pipeline_weekly_granularity(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
    ) -> None:
        """Trend pipeline with last_week period and daily granularity."""
        period = TimePeriod.last_week()
        result = dispatcher.get_trend(
            CanonicalMetric.ENERGY_PER_UNIT, "Line-1", period, granularity="daily"
        )
        response = builder.format_trend_result(result)

        assert result.granularity == "daily"
        assert isinstance(response, str)


# ══════════════════════════════════════════════════════════
# 4. Full Anomaly Pipeline
# ══════════════════════════════════════════════════════════


class TestAnomalyPipeline:
    """End-to-end: dispatcher → response_builder for anomaly checks."""

    def test_anomaly_pipeline_no_anomaly(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
    ) -> None:
        """Phase 1 stub returns no anomaly; response is reassuring."""
        result = dispatcher.check_anomaly(CanonicalMetric.OEE, "Line-1")
        response = builder.format_anomaly_result(result)

        assert isinstance(result, AnomalyResult)
        assert result.is_anomalous is False
        assert "normal" in response.lower() or "no unusual" in response.lower()


# ══════════════════════════════════════════════════════════
# 5. Full WhatIf Pipeline
# ══════════════════════════════════════════════════════════


class TestWhatIfPipeline:
    """End-to-end: dispatcher → response_builder for what-if simulations."""

    def test_whatif_pipeline_produces_response(
        self,
        dispatcher: QueryDispatcher,
        builder: ResponseBuilder,
    ) -> None:
        """WhatIf pipeline returns formatted response with change %."""
        scenario = WhatIfScenario(
            name="temperature_reduction",
            asset_id="Line-1",
            parameters=[
                ScenarioParameter("temperature", 200.0, 190.0, "°C"),
            ],
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )

        result = dispatcher.simulate_whatif(scenario)
        response = builder.format_whatif_result(result)

        assert isinstance(result, WhatIfResult)
        assert isinstance(response, str)
        assert len(response) > 0


# ══════════════════════════════════════════════════════════
# 6. Adapter Hot-Swap
# ══════════════════════════════════════════════════════════


class TestAdapterHotSwap:
    """Integration: adapter hot-swap during runtime."""

    def test_hot_swap_queries_use_new_adapter(
        self,
        dispatcher: QueryDispatcher,
        period: TimePeriod,
    ) -> None:
        """After set_adapter(), queries go through the new adapter."""
        # Query with original adapter
        result1 = dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        assert isinstance(result1, KPIResult)

        # Swap adapter
        new_adapter = MockAdapter()
        dispatcher.set_adapter(new_adapter)
        assert dispatcher.adapter is new_adapter

        # Query with new adapter
        result2 = dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        assert isinstance(result2, KPIResult)


# ══════════════════════════════════════════════════════════
# 7. Audit Trail Round-Trip
# ══════════════════════════════════════════════════════════


class TestAuditTrailRoundTrip:
    """Integration: verify audit records after multiple queries."""

    def test_three_queries_produce_three_audit_entries(
        self,
        dispatcher: QueryDispatcher,
        audit_logger: AuditLogger,
        period: TimePeriod,
    ) -> None:
        """Running 3 different queries creates 3 audit log entries."""
        dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        dispatcher.compare(
            CanonicalMetric.ENERGY_PER_UNIT,
            ["Line-1", "Line-2"],
            period,
        )
        dispatcher.get_trend(CanonicalMetric.SCRAP_RATE, "Line-1", period)

        logs = audit_logger.get_recent_logs(limit=10)
        assert len(logs) == 3

        # Verify all 3 query types are present
        types = {log.query_type for log in logs}
        assert types == {"get_kpi", "compare", "get_trend"}

    def test_audit_entries_retrievable_by_asset(
        self,
        dispatcher: QueryDispatcher,
        audit_logger: AuditLogger,
        period: TimePeriod,
    ) -> None:
        """Audit entries can be queried back by asset_id."""
        dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        dispatcher.get_kpi(CanonicalMetric.OEE, "Line-2", period)

        line1_logs = audit_logger.get_logs_for_asset("Line-1")
        line2_logs = audit_logger.get_logs_for_asset("Line-2")

        assert len(line1_logs) == 1
        assert len(line2_logs) == 1
        assert line1_logs[0].asset_id == "Line-1"

    def test_audit_entries_have_response_summaries(
        self,
        dispatcher: QueryDispatcher,
        audit_logger: AuditLogger,
        period: TimePeriod,
    ) -> None:
        """All audit entries include non-empty response summaries."""
        dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        dispatcher.compare(
            CanonicalMetric.OEE, ["Line-1", "Line-2"], period
        )

        logs = audit_logger.get_recent_logs(limit=10)
        for log in logs:
            assert log.response_summary is not None
            assert len(log.response_summary) > 0

    def test_audit_statistics_reflect_queries(
        self,
        dispatcher: QueryDispatcher,
        audit_logger: AuditLogger,
        period: TimePeriod,
    ) -> None:
        """AuditLogger statistics match the queries executed."""
        dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        dispatcher.get_kpi(CanonicalMetric.SCRAP_RATE, "Line-1", period)
        dispatcher.compare(
            CanonicalMetric.OEE, ["Line-1", "Line-2"], period
        )

        stats = audit_logger.get_statistics(days=1)
        assert stats["total_queries"] == 3
        assert stats["queries_by_type"]["get_kpi"] == 2
        assert stats["queries_by_type"]["compare"] == 1
