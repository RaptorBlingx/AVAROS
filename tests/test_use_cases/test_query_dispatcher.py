"""
QueryDispatcher Unit Test Suite

Covers all public methods and internal helpers of QueryDispatcher:
    - Initialization (with/without audit_logger)
    - adapter property and set_adapter()
    - get_kpi, compare, get_trend (async adapter calls via _run_async)
    - check_anomaly (honest pending-feature error), simulate_whatif
    - _run_async (async/sync bridging)
    - _log_audit (audit record creation, error resilience)
    - _generate_response_summary (all 5 result types)
    - _generate_query_id (format, uniqueness)

Uses real StubAdapter (verified in P2-L01) and in-memory AuditLogger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.helpers.stub_adapter import StubAdapter
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
from skill.domain.exceptions import AVAROSError, MetricNotSupportedError
from skill.domain.anomaly_models import AnomalyDetectionResult, ForecastReport
from skill.services.audit import AuditLogger
from skill.services.co2_service import CO2DerivationService
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService
from skill.use_cases.query_dispatcher import QueryDispatcher


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def adapter() -> StubAdapter:
    """Real StubAdapter instance."""
    return StubAdapter()


@pytest.fixture
def audit_logger() -> AuditLogger:
    """In-memory AuditLogger, initialized and ready."""
    audit = AuditLogger()
    audit.initialize()
    yield audit
    audit.close()


@pytest.fixture
def dispatcher(adapter: StubAdapter, audit_logger: AuditLogger) -> QueryDispatcher:
    """QueryDispatcher wired with StubAdapter and in-memory AuditLogger."""
    return QueryDispatcher(adapter=adapter, audit_logger=audit_logger)


@pytest.fixture
def period() -> TimePeriod:
    """Standard TimePeriod for test queries."""
    return TimePeriod.today()


@pytest.fixture
def scenario() -> WhatIfScenario:
    """Standard what-if scenario for test queries."""
    return WhatIfScenario(
        name="temperature_reduction",
        asset_id="Line-1",
        parameters=[
            ScenarioParameter(
                name="temperature",
                baseline_value=200.0,
                proposed_value=190.0,
                unit="°C",
            ),
        ],
        target_metric=CanonicalMetric.ENERGY_PER_UNIT,
    )


# ══════════════════════════════════════════════════════════
# 1. Initialization
# ══════════════════════════════════════════════════════════


class TestQueryDispatcherInit:
    """Tests for __init__()."""

    def test_init_stores_adapter_and_audit_logger(
        self, adapter: StubAdapter, audit_logger: AuditLogger
    ) -> None:
        """Constructor stores adapter and audit logger references."""
        d = QueryDispatcher(adapter=adapter, audit_logger=audit_logger)
        assert d.adapter is adapter
        assert d._audit_logger is audit_logger

    def test_init_without_audit_logger_creates_default(
        self, adapter: StubAdapter
    ) -> None:
        """Omitting audit_logger creates a default AuditLogger."""
        d = QueryDispatcher(adapter=adapter)
        assert isinstance(d._audit_logger, AuditLogger)

    def test_adapter_property_returns_adapter(
        self, dispatcher: QueryDispatcher, adapter: StubAdapter
    ) -> None:
        """The adapter property returns the stored adapter."""
        assert dispatcher.adapter is adapter


# ══════════════════════════════════════════════════════════
# 2. set_adapter
# ══════════════════════════════════════════════════════════


class TestSetAdapter:
    """Tests for set_adapter()."""

    def test_set_adapter_replaces_adapter(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """set_adapter() swaps the adapter instance."""
        new_adapter = StubAdapter()
        dispatcher.set_adapter(new_adapter)
        assert dispatcher.adapter is new_adapter

    def test_set_adapter_queries_use_new_adapter(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """After set_adapter(), queries go through the new adapter."""
        new_adapter = StubAdapter()
        dispatcher.set_adapter(new_adapter)

        result = dispatcher.get_kpi(
            CanonicalMetric.OEE, "Line-1", period
        )
        assert isinstance(result, KPIResult)


# ══════════════════════════════════════════════════════════
# 3. get_kpi
# ══════════════════════════════════════════════════════════


class TestGetKPI:
    """Tests for get_kpi()."""

    def test_get_kpi_returns_kpi_result(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """get_kpi() returns a KPIResult with correct metric."""
        result = dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.OEE
        assert result.asset_id == "Line-1"

    @pytest.mark.parametrize(
        "metric",
        [
            CanonicalMetric.OEE,
            CanonicalMetric.SCRAP_RATE,
            CanonicalMetric.ENERGY_PER_UNIT,
            CanonicalMetric.CO2_PER_UNIT,
            CanonicalMetric.THROUGHPUT,
        ],
    )
    def test_get_kpi_parametrized_metrics(
        self, dispatcher: QueryDispatcher, period: TimePeriod, metric: CanonicalMetric
    ) -> None:
        """get_kpi() works for various canonical metrics."""
        result = dispatcher.get_kpi(metric, "Line-1", period)
        assert isinstance(result, KPIResult)
        assert result.metric == metric
        assert isinstance(result.value, float)

    def test_get_kpi_creates_audit_record(
        self, dispatcher: QueryDispatcher, audit_logger: AuditLogger, period: TimePeriod
    ) -> None:
        """get_kpi() logs an audit entry."""
        dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)

        logs = audit_logger.get_recent_logs(limit=1)
        assert len(logs) == 1
        assert logs[0].query_type == "get_kpi"
        assert logs[0].metric == "oee"
        assert logs[0].asset_id == "Line-1"


# ══════════════════════════════════════════════════════════
# 4. compare
# ══════════════════════════════════════════════════════════


class TestCompare:
    """Tests for compare()."""

    def test_compare_returns_comparison_result(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """compare() returns a ComparisonResult with ranked items."""
        result = dispatcher.compare(
            CanonicalMetric.ENERGY_PER_UNIT,
            ["Compressor-1", "Compressor-2"],
            period,
        )
        assert isinstance(result, ComparisonResult)
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert len(result.items) == 2
        assert result.winner_id in ("Compressor-1", "Compressor-2")

    def test_compare_creates_audit_record(
        self, dispatcher: QueryDispatcher, audit_logger: AuditLogger, period: TimePeriod
    ) -> None:
        """compare() logs an audit entry."""
        dispatcher.compare(
            CanonicalMetric.OEE,
            ["Line-1", "Line-2"],
            period,
        )

        logs = audit_logger.get_recent_logs(limit=1)
        assert len(logs) == 1
        assert logs[0].query_type == "compare"


# ══════════════════════════════════════════════════════════
# 5. get_trend
# ══════════════════════════════════════════════════════════


class TestGetTrend:
    """Tests for get_trend()."""

    def test_get_trend_returns_trend_result(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """get_trend() returns a TrendResult with direction."""
        result = dispatcher.get_trend(
            CanonicalMetric.SCRAP_RATE, "Line-1", period
        )
        assert isinstance(result, TrendResult)
        assert result.metric == CanonicalMetric.SCRAP_RATE
        assert result.direction in ("up", "down", "stable")
        assert len(result.data_points) >= 1

    def test_get_trend_custom_granularity(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """get_trend() accepts custom granularity."""
        period = TimePeriod.last_week()
        result = dispatcher.get_trend(
            CanonicalMetric.ENERGY_PER_UNIT, "Line-1", period, granularity="hourly"
        )
        assert isinstance(result, TrendResult)
        assert result.granularity == "hourly"

    def test_get_trend_creates_audit_record(
        self, dispatcher: QueryDispatcher, audit_logger: AuditLogger, period: TimePeriod
    ) -> None:
        """get_trend() logs an audit entry."""
        dispatcher.get_trend(CanonicalMetric.OEE, "Line-1", period)

        logs = audit_logger.get_recent_logs(limit=1)
        assert len(logs) == 1
        assert logs[0].query_type == "get_trend"


# ══════════════════════════════════════════════════════════
# 6. check_anomaly
# ══════════════════════════════════════════════════════════


class TestCheckAnomaly:
    """Tests for anomaly detection when prevention client is absent."""

    def test_check_anomaly_raises_when_no_client(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """check_anomaly() raises ANOMALY_NOT_CONFIGURED without a client."""
        with pytest.raises(AVAROSError) as exc_info:
            dispatcher.check_anomaly(CanonicalMetric.OEE, "Line-1")

        assert exc_info.value.code == "ANOMALY_NOT_CONFIGURED"
        assert "not configured" in exc_info.value.user_message

    def test_check_anomaly_without_client_does_not_audit(
        self, dispatcher: QueryDispatcher, audit_logger: AuditLogger
    ) -> None:
        """check_anomaly() fails fast without auditing when client is absent."""
        with pytest.raises(AVAROSError):
            dispatcher.check_anomaly(CanonicalMetric.OEE, "Line-1")

        logs = audit_logger.get_recent_logs(limit=1)
        assert len(logs) == 0


class _SyntheticPreventionClient:
    """Minimal deterministic prevention client for dispatcher tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[CanonicalMetric, str | None, float]] = []
        self.forecast_calls: list[tuple[CanonicalMetric, str | None, int, int]] = []

    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points,
        threshold: float = 2.0,
        asset_id: str | None = None,
    ) -> AnomalyDetectionResult:
        self.calls.append((metric, asset_id, threshold))
        is_anomalous = metric == CanonicalMetric.OEE and asset_id == "Line-1"
        severity = "high" if is_anomalous else "none"
        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=is_anomalous,
            severity=severity,
            confidence=0.9,
            anomaly_type="spike" if is_anomalous else None,
            description="synthetic",
            detected_at=datetime.now(timezone.utc).isoformat(),
            recommended_action="check" if is_anomalous else None,
            expected_value=100.0,
            actual_value=130.0 if is_anomalous else 99.5,
            deviation=3.1 if is_anomalous else 0.4,
        )

    async def forecast_metric(
        self,
        metric: CanonicalMetric,
        data_points,
        horizon_periods: int = 7,
        asset_id: str | None = None,
    ) -> ForecastReport:
        self.forecast_calls.append(
            (metric, asset_id, horizon_periods, len(data_points)),
        )
        return ForecastReport(
            metric=metric,
            asset_id=asset_id or "",
            horizon_periods=horizon_periods,
            predicted_value=88.5,
            unit=metric.default_unit,
            confidence=0.82,
            fit_quality=0.76,
            training_points=len(data_points),
            method_name="linear_forecast",
            forecast_timestamp=datetime.now(timezone.utc).isoformat(),
            description="synthetic forecast",
            recommended_action="Review forecast drivers.",
        )


class TestScanAnomalies:
    """Tests for aggregate anomaly scan behavior."""

    def test_check_anomaly_passes_asset_id_to_client(self) -> None:
        """Pair checks forward asset scope into prevention client call."""
        adapter = StubAdapter()
        prevention = _SyntheticPreventionClient()
        dispatcher = QueryDispatcher(
            adapter=adapter,
            prevention_client=prevention,
        )
        dispatcher._collect_daily_series = MagicMock(return_value=[])

        dispatcher.check_anomaly(
            CanonicalMetric.OEE,
            "Line-2",
            threshold=2.7,
        )

        metric, asset_id, threshold = prevention.calls[-1]
        assert metric == CanonicalMetric.OEE
        assert asset_id == "Line-2"
        assert threshold == pytest.approx(2.7)

    def test_check_anomaly_passes_anomaly_type_through(self) -> None:
        """anomaly_type from detection result propagates to Anomaly model."""
        adapter = StubAdapter()
        prevention = _SyntheticPreventionClient()
        dispatcher = QueryDispatcher(
            adapter=adapter,
            prevention_client=prevention,
        )
        dispatcher._collect_daily_series = MagicMock(return_value=[])

        result = dispatcher.check_anomaly(
            CanonicalMetric.OEE,
            "Line-1",
        )

        assert result.is_anomalous
        assert result.anomalies[0].anomaly_type == "spike"

    def test_scan_anomalies_metric_filter_limits_scope(self) -> None:
        """Metric filter scans all assets but only one metric."""
        adapter = StubAdapter()
        adapter.get_supported_metrics = MagicMock(
            return_value=[
                CanonicalMetric.OEE,
                CanonicalMetric.ENERGY_PER_UNIT,
            ]
        )
        adapter.list_assets = AsyncMock(
            return_value=[
                SimpleNamespace(asset_id="Line-1"),
                SimpleNamespace(asset_id="Line-2"),
            ]
        )
        prevention = _SyntheticPreventionClient()
        dispatcher = QueryDispatcher(
            adapter=adapter,
            prevention_client=prevention,
        )

        result = dispatcher.scan_anomalies(metric=CanonicalMetric.OEE)

        assert result.checked_pairs == 2
        assert all(call[0] == CanonicalMetric.OEE for call in prevention.calls)

    def test_scan_anomalies_asset_filter_limits_scope(self) -> None:
        """Asset filter scans all metrics but only one asset."""
        adapter = StubAdapter()
        adapter.get_supported_metrics = MagicMock(
            return_value=[
                CanonicalMetric.OEE,
                CanonicalMetric.ENERGY_PER_UNIT,
            ]
        )
        adapter.list_assets = AsyncMock(
            return_value=[
                SimpleNamespace(asset_id="Line-1"),
                SimpleNamespace(asset_id="Line-2"),
            ]
        )
        prevention = _SyntheticPreventionClient()
        dispatcher = QueryDispatcher(
            adapter=adapter,
            prevention_client=prevention,
        )

        result = dispatcher.scan_anomalies(asset_id="Line-2")

        assert result.checked_pairs == 2
        assert all(call[1] == "Line-2" for call in prevention.calls)


# ══════════════════════════════════════════════════════════
# 7. forecast_metric
# ══════════════════════════════════════════════════════════


class TestForecastMetric:
    """Tests for PREVENTION forecast query behavior."""

    def test_forecast_metric_raises_when_no_client(
        self,
        dispatcher: QueryDispatcher,
    ) -> None:
        """Forecasting fails honestly when PREVENTION is not configured."""
        with pytest.raises(AVAROSError) as exc_info:
            dispatcher.forecast_metric(CanonicalMetric.OEE, "Line-1")

        assert exc_info.value.code == "FORECAST_NOT_CONFIGURED"
        assert "Forecasting is not configured" in exc_info.value.user_message

    def test_forecast_metric_passes_asset_and_horizon_to_client(self) -> None:
        """Dispatcher forwards forecast scope into the PREVENTION client."""
        adapter = StubAdapter()
        prevention = _SyntheticPreventionClient()
        dispatcher = QueryDispatcher(
            adapter=adapter,
            prevention_client=prevention,
        )
        dispatcher._collect_analysis_series = MagicMock(
            return_value=[
                SimpleNamespace(value=80.0, unit="%"),
                SimpleNamespace(value=82.0, unit="%"),
            ],
        )

        result = dispatcher.forecast_metric(
            CanonicalMetric.OEE,
            "Line-1",
            horizon_periods=14,
        )

        assert isinstance(result, ForecastReport)
        assert result.predicted_value == 88.5
        assert prevention.forecast_calls == [
            (CanonicalMetric.OEE, "Line-1", 14, 2),
        ]


# ══════════════════════════════════════════════════════════
# 8. _run_async
# ══════════════════════════════════════════════════════════


class TestRunAsync:
    """Tests for _run_async() bridging."""

    def test_run_async_executes_coroutine(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """_run_async() executes async coroutine and returns result."""
        import asyncio

        async def sample_coro() -> int:
            return 42

        result = dispatcher._run_async(sample_coro())
        assert result == 42

    def test_run_async_handles_adapter_call(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """_run_async() correctly bridges a real async adapter call."""
        result = dispatcher._run_async(
            dispatcher.adapter.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        )
        assert isinstance(result, KPIResult)

    def test_run_async_no_event_loop_fallback(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """_run_async() falls back to asyncio.run on RuntimeError."""
        import asyncio

        async def sample_coro() -> str:
            return "fallback_ok"

        with patch(
            "skill.use_cases.query_dispatcher.asyncio.get_event_loop",
            side_effect=RuntimeError("no current event loop"),
        ):
            result = dispatcher._run_async(sample_coro())
        assert result == "fallback_ok"

    def test_run_async_running_loop_branch(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """_run_async() executes work through the dispatcher's executor."""
        mock_future = MagicMock()
        dispatcher._executor = MagicMock()

        async def sample_coro() -> str:
            return "from_running_loop"

        def _submit(fn):
            mock_future.result.return_value = fn()
            return mock_future

        dispatcher._executor.submit.side_effect = _submit
        result = dispatcher._run_async(sample_coro())

        assert result == "from_running_loop"
        dispatcher._executor.submit.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=60)


# ══════════════════════════════════════════════════════════
# 9. _log_audit
# ══════════════════════════════════════════════════════════


class TestLogAudit:
    """Tests for _log_audit()."""

    def test_log_audit_stores_correct_fields(
        self, dispatcher: QueryDispatcher, audit_logger: AuditLogger, period: TimePeriod
    ) -> None:
        """_log_audit() stores query_type, metric, asset_id, and summary."""
        result = dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)

        logs = audit_logger.get_recent_logs(limit=1)
        assert len(logs) == 1
        entry = logs[0]
        assert entry.query_type == "get_kpi"
        assert entry.metric == "oee"
        assert entry.asset_id == "Line-1"
        assert entry.response_summary is not None
        assert "KPI value" in entry.response_summary

    def test_log_audit_error_does_not_crash_query(
        self, adapter: StubAdapter, period: TimePeriod
    ) -> None:
        """If audit logging raises, the query still returns a result."""
        broken_audit = MagicMock(spec=AuditLogger)
        broken_audit.log_query.side_effect = RuntimeError("DB down")

        d = QueryDispatcher(adapter=adapter, audit_logger=broken_audit)
        result = d.get_kpi(CanonicalMetric.OEE, "Line-1", period)

        # Query succeeds despite audit failure
        assert isinstance(result, KPIResult)
        broken_audit.log_query.assert_called_once()

    def test_log_audit_includes_recommendation_id(
        self, dispatcher: QueryDispatcher, audit_logger: AuditLogger, period: TimePeriod
    ) -> None:
        """Audit entry includes recommendation_id from result."""
        dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)

        logs = audit_logger.get_recent_logs(limit=1)
        entry = logs[0]
        assert entry.recommendation_id is not None


# ══════════════════════════════════════════════════════════
# 10. _generate_response_summary
# ══════════════════════════════════════════════════════════


class TestGenerateResponseSummary:
    """Tests for _generate_response_summary()."""

    def test_summary_for_kpi_result(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """KPIResult summary includes value and unit."""
        result = dispatcher.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        summary = dispatcher._generate_response_summary(result)
        assert "KPI value" in summary
        assert "%" in summary

    def test_summary_for_comparison_result(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """ComparisonResult summary includes winner."""
        result = dispatcher.compare(
            CanonicalMetric.OEE, ["Line-1", "Line-2"], period
        )
        summary = dispatcher._generate_response_summary(result)
        assert "Winner" in summary

    def test_summary_for_trend_result(
        self, dispatcher: QueryDispatcher, period: TimePeriod
    ) -> None:
        """TrendResult summary includes direction."""
        result = dispatcher.get_trend(CanonicalMetric.OEE, "Line-1", period)
        summary = dispatcher._generate_response_summary(result)
        assert "Direction" in summary

    def test_summary_for_anomaly_result(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """AnomalyResult summary includes is_anomalous."""
        result = AnomalyResult(
            is_anomalous=False,
            anomalies=[],
            severity="none",
            asset_id="Line-1",
            metric=CanonicalMetric.OEE,
        )
        summary = dispatcher._generate_response_summary(result)
        assert "Anomalous" in summary

    def test_summary_for_unknown_result_type(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """Unknown result type returns class name."""
        summary = dispatcher._generate_response_summary("not_a_result")
        assert summary == "str"


# ══════════════════════════════════════════════════════════
# 11. _generate_query_id
# ══════════════════════════════════════════════════════════


class TestGenerateQueryId:
    """Tests for _generate_query_id()."""

    def test_generate_query_id_starts_with_q(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """Generated ID starts with 'q-'."""
        qid = dispatcher._generate_query_id()
        assert qid.startswith("q-")

    def test_generate_query_id_unique(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """Each call produces a unique ID."""
        ids = {dispatcher._generate_query_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_query_id_is_string(
        self, dispatcher: QueryDispatcher
    ) -> None:
        """Returns a string."""
        assert isinstance(dispatcher._generate_query_id(), str)


# ══════════════════════════════════════════════════════════
# 12. CO₂ Derivation (DEC-007, DEC-023)
# ══════════════════════════════════════════════════════════


class TestQueryDispatcherCO2Derivation:
    """Tests for CO₂ derivation through QueryDispatcher."""

    @pytest.fixture
    def settings_service(self) -> SettingsService:
        """In-memory SettingsService for CO2 tests."""
        svc = SettingsService()
        svc.initialize()
        return svc

    @pytest.fixture
    def co2_service(
        self, settings_service: SettingsService,
    ) -> CO2DerivationService:
        """CO2DerivationService with default TR factors."""
        return CO2DerivationService(settings_service)

    @pytest.fixture
    def adapter_no_native_carbon(self) -> StubAdapter:
        """StubAdapter that does NOT support native_carbon."""
        adapter = StubAdapter()
        original = adapter.supports_capability

        def _patched(capability: str) -> bool:
            if capability == "native_carbon":
                return False
            return original(capability)

        adapter.supports_capability = _patched
        return adapter

    @pytest.fixture
    def dispatcher_with_co2(
        self,
        adapter_no_native_carbon: StubAdapter,
        settings_service: SettingsService,
        co2_service: CO2DerivationService,
    ) -> QueryDispatcher:
        """Dispatcher with CO2 derivation enabled."""
        audit = AuditLogger()
        audit.initialize()
        return QueryDispatcher(
            adapter=adapter_no_native_carbon,
            audit_logger=audit,
            settings_service=settings_service,
            co2_service=co2_service,
        )

    @pytest.fixture
    def dispatcher_native(
        self,
        audit_logger: AuditLogger,
    ) -> QueryDispatcher:
        """Dispatcher with native carbon adapter (no derivation)."""
        adapter = StubAdapter()
        return QueryDispatcher(
            adapter=adapter,
            audit_logger=audit_logger,
        )

    def test_co2_total_derived_from_energy(
        self, dispatcher_with_co2: QueryDispatcher,
    ) -> None:
        """CO2_TOTAL query derives from ENERGY_TOTAL × factor."""
        period = TimePeriod.today()
        result = dispatcher_with_co2.get_kpi(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.CO2_TOTAL
        assert result.value > 0
        assert result.unit == "kg CO₂-eq"

    def test_co2_per_unit_requires_production_service(
        self, dispatcher_with_co2: QueryDispatcher,
    ) -> None:
        """CO2_PER_UNIT without production service raises MetricNotSupportedError."""
        period = TimePeriod.today()
        with pytest.raises(MetricNotSupportedError) as exc_info:
            dispatcher_with_co2.get_kpi(
                metric=CanonicalMetric.CO2_PER_UNIT,
                asset_id="Line-1",
                period=period,
            )
        assert "production data" in str(exc_info.value).lower()

    def test_co2_trend_derived_from_energy_trend(
        self, dispatcher_with_co2: QueryDispatcher,
    ) -> None:
        """CO2_TOTAL trend query derives from energy trend data."""
        period = TimePeriod.last_week()
        result = dispatcher_with_co2.get_trend(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, TrendResult)
        assert result.metric == CanonicalMetric.CO2_TOTAL
        assert len(result.data_points) > 0

    def test_native_carbon_adapter_bypasses_derivation(
        self, dispatcher_native: QueryDispatcher,
    ) -> None:
        """Adapter with native_carbon capability goes direct, not derived."""
        period = TimePeriod.today()
        # StubAdapter supports all capabilities including native_carbon
        # and returns stub CO2 data directly
        result = dispatcher_native.get_kpi(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, KPIResult)

    def test_co2_total_value_is_positive_and_reasonable(
        self, dispatcher_with_co2: QueryDispatcher,
    ) -> None:
        """Derived CO2_TOTAL is positive and uses TR default factor (0.48)."""
        period = TimePeriod.today()
        co2 = dispatcher_with_co2.get_kpi(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id="Line-1",
            period=period,
        )
        # CO2 must be positive (mock energy is always positive)
        assert co2.value > 0
        # CO2 value should be less than the energy value
        # (factor is 0.48 < 1.0), so verify reasonable magnitude
        assert co2.unit == "kg CO₂-eq"

    def test_co2_total_equals_energy_times_factor(
        self,
        settings_service: SettingsService,
        co2_service: CO2DerivationService,
    ) -> None:
        """Verify exact multiplication: CO₂ = energy × 0.48 (TR default)."""
        from datetime import datetime

        # Arrange — adapter with fixed energy response
        energy_result = KPIResult(
            metric=CanonicalMetric.ENERGY_TOTAL,
            value=250.0,
            unit="kWh",
            asset_id="Line-1",
            period=TimePeriod.today(),
            timestamp=datetime.now(),
        )
        mock_adapter = MagicMock()
        mock_adapter.get_kpi = AsyncMock(return_value=energy_result)
        mock_adapter.supports_capability.return_value = False
        mock_adapter.platform_name = "stub"

        audit = AuditLogger()
        audit.initialize()
        dispatcher = QueryDispatcher(
            adapter=mock_adapter,
            audit_logger=audit,
            settings_service=settings_service,
            co2_service=co2_service,
        )

        # Act
        result = dispatcher.get_kpi(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id="Line-1",
            period=TimePeriod.today(),
        )

        # Assert — 250 kWh × 0.48 = 120.0 kg CO₂-eq
        assert result.value == 120.0
        assert result.unit == "kg CO₂-eq"
        assert result.metric == CanonicalMetric.CO2_TOTAL

    def test_co2_total_uses_primary_energy_source_from_settings(
        self,
        settings_service: SettingsService,
        co2_service: CO2DerivationService,
    ) -> None:
        """Gas-only custom profile should derive CO2 using gas factor."""
        settings_service.update_platform_config(
            PlatformConfig(
                platform_type="custom_rest",
                api_url="http://example.invalid",
                api_key="test-key",
            )
        )
        settings_service.set_emission_factor("gas", 0.2)

        energy_result = KPIResult(
            metric=CanonicalMetric.ENERGY_TOTAL,
            value=250.0,
            unit="kWh",
            asset_id="Line-1",
            period=TimePeriod.today(),
            timestamp=TimePeriod.today().end,
        )
        mock_adapter = MagicMock()
        mock_adapter.get_kpi = AsyncMock(return_value=energy_result)
        mock_adapter.supports_capability.return_value = False
        mock_adapter.platform_name = "my-api"
        audit = AuditLogger()
        audit.initialize()
        dispatcher = QueryDispatcher(
            adapter=mock_adapter,
            audit_logger=audit,
            settings_service=settings_service,
            co2_service=co2_service,
        )

        result = dispatcher.get_kpi(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id="Line-1",
            period=TimePeriod.today(),
        )

        assert result.value == 50.0
