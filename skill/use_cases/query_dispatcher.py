"""
QueryDispatcher - Routes Queries to Adapter Methods

Central orchestrator that routes the 5 query types to the appropriate
adapter method. Provides a synchronous interface for OVOS handlers
while managing async adapter calls internally.

Responsibilities:
    - Route queries to correct adapter method
    - Handle async/sync bridging
    - Apply common pre/post processing
    - Audit logging for compliance

Design Pattern:
    This is a Facade that simplifies adapter interaction for skill handlers.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections import Counter
import logging
from datetime import datetime, timedelta, timezone
import re
from typing import TYPE_CHECKING
import uuid

from skill.domain.exceptions import AVAROSError, MetricNotSupportedError
from skill.domain.models import (
    Anomaly,
    CanonicalMetric,
    DataPoint,
    ScenarioParameter,
    TimePeriod,
    WhatIfScenario,
)
from skill.domain.results import (
    AnomalyResult,
    AnomalyScanResult,
    KPIResult,
    WhatIfResult,
)
from skill.services.audit import AuditLogger

if TYPE_CHECKING:
    from skill.adapters.base import ManufacturingAdapter
    from skill.clients.prevention import PreventionClient
    from skill.domain.anomaly_models import DriftReport, ForecastReport
    from skill.domain.models import TimePeriod
    from skill.domain.production import ProductionSummary
    from skill.domain.results import ComparisonResult, TrendResult
    from skill.services.co2_service import CO2DerivationService
    from skill.services.production_data import ProductionDataService
    from skill.services.settings import SettingsService


logger = logging.getLogger(__name__)


class QueryDispatcher:
    """
    Routes manufacturing queries to the appropriate adapter method.
    
    This class acts as a facade between OVOS intent handlers and
    platform adapters. It handles:
    
    1. Async/sync bridging (OVOS handlers are sync, adapters are async)
    2. Query routing to the 5 query types
    3. Audit logging for GDPR compliance
    4. Error handling and user-friendly messages
    
    Attributes:
        adapter: The platform adapter to route queries to
        _loop: Event loop for async operations
    
    Example:
        dispatcher = QueryDispatcher(adapter=mock_adapter)
        
        # Sync call from OVOS handler
        result = dispatcher.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=TimePeriod.today()
        )
    """
    
    _DERIVED_CARBON_METRICS = frozenset({
        CanonicalMetric.CO2_TOTAL,
        CanonicalMetric.CO2_PER_UNIT,
        CanonicalMetric.CO2_PER_BATCH,
    })

    _DERIVED_SUPPLEMENTARY_METRICS = frozenset({
        CanonicalMetric.ENERGY_PER_UNIT,
        CanonicalMetric.MATERIAL_EFFICIENCY,
    })
    
    def __init__(
        self,
        adapter: ManufacturingAdapter,
        audit_logger: AuditLogger | None = None,
        co2_service: CO2DerivationService | None = None,
        production_data_service: ProductionDataService | None = None,
        settings_service: SettingsService | None = None,
        prevention_client: PreventionClient | None = None,
    ) -> None:
        """
        Initialize dispatcher with an adapter.
        
        Args:
            adapter: ManufacturingAdapter instance to route queries to
            audit_logger: Optional AuditLogger for compliance logging
            co2_service: Optional CO2DerivationService for derived metrics
            production_data_service: Optional ProductionDataService for
                supplementary data (production counts, material usage)
            settings_service: Optional SettingsService for profile-driven
                energy source resolution in CO₂ derivation
            prevention_client: Optional PreventionClient for anomaly
                detection and drift monitoring
        """
        self._adapter = adapter
        self._audit_logger = audit_logger or AuditLogger()
        self._co2_service = co2_service
        self._production_service = production_data_service
        self._settings_service = settings_service
        self._prevention_client = prevention_client
        self._loop: asyncio.AbstractEventLoop | None = None
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="avaros-dispatcher",
        )
    
    @property
    def adapter(self) -> ManufacturingAdapter:
        """Get the current adapter."""
        return self._adapter
    
    def set_adapter(self, adapter: ManufacturingAdapter) -> None:
        """
        Replace the adapter (for hot-reload support).
        
        Args:
            adapter: New adapter instance
        """
        logger.info(
            "Switching adapter from %s to %s",
            type(self._adapter).__name__,
            type(adapter).__name__,
        )
        self._adapter = adapter
    
    # =========================================================================
    # Query Type 1: KPI Retrieval
    # =========================================================================
    
    def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """
        Retrieve a KPI value (synchronous wrapper).
        
        This is the primary interface for OVOS intent handlers.
        
        Args:
            metric: Canonical metric to retrieve
            asset_id: Target asset identifier
            period: Time period for measurement
            
        Returns:
            KPIResult with value and metadata
            
        Example:
            result = dispatcher.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id="Line-1",
                period=TimePeriod.today()
            )
            speak(f"OEE is {result.value} percent")
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] get_kpi: metric=%s, asset=%s, period=%s",
            query_id, metric.value, asset_id, period.display_name,
        )

        self._ensure_metric_supported_for_asset(metric, asset_id)

        # Intercept derived carbon metrics (DEC-007, DEC-023)
        if self._is_derived_carbon_metric(metric) and self._co2_service:
            result = self._derive_carbon_kpi(
                metric, asset_id, period,
            )
            self._log_audit(
                "get_kpi", query_id, metric.value, asset_id, result,
            )
            return result

        # Intercept supplementary-derived metrics (DEC-023)
        if self._is_derived_supplementary_metric(metric):
            result = self._derive_supplementary_kpi(
                metric, asset_id, period,
            )
            self._log_audit(
                "get_kpi", query_id, metric.value, asset_id, result,
            )
            return result
        
        result = self._run_async(
            self._adapter.get_kpi(metric, asset_id, period)
        )
        
        self._log_audit("get_kpi", query_id, metric.value, asset_id, result)
        return result
    
    # =========================================================================
    # Query Type 2: Comparison
    # =========================================================================
    
    def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        """
        Compare a metric across multiple assets (synchronous wrapper).
        
        Args:
            metric: Canonical metric to compare
            asset_ids: List of asset identifiers (2+)
            period: Time period for comparison
            
        Returns:
            ComparisonResult with ranked items and winner
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] compare: metric=%s, assets=%s, period=%s",
            query_id, metric.value, asset_ids, period.display_name,
        )
        
        result = self._run_async(
            self._adapter.compare(metric, asset_ids, period)
        )
        
        self._log_audit("compare", query_id, metric.value, str(asset_ids), result)
        return result
    
    # =========================================================================
    # Query Type 3: Trend Analysis
    # =========================================================================
    
    def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """
        Get trend data for a metric (synchronous wrapper).
        
        Args:
            metric: Canonical metric to trend
            asset_id: Target asset identifier
            period: Time period to analyze
            granularity: Data frequency ("hourly", "daily", "weekly")
            
        Returns:
            TrendResult with data points and trend direction
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] get_trend: metric=%s, asset=%s, period=%s, granularity=%s",
            query_id, metric.value, asset_id, period.display_name, granularity,
        )
        
        # Intercept derived carbon trend (DEC-007, DEC-023)
        if self._is_derived_carbon_metric(metric) and self._co2_service:
            result = self._derive_carbon_trend(
                metric, asset_id, period, granularity,
            )
            self._log_audit(
                "get_trend", query_id, metric.value, asset_id, result,
            )
            return result

        result = self._run_async(
            self._adapter.get_trend(metric, asset_id, period, granularity)
        )
        
        self._log_audit("get_trend", query_id, metric.value, asset_id, result)
        return result
    
    # =========================================================================
    # Query Type 4: Anomaly Detection (PREVENTION Integration)
    # =========================================================================
    
    def check_anomaly(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        threshold: float | None = None,
    ) -> AnomalyResult:
        """
        Check a metric for anomalies using statistical analysis.
        
        Fetches raw data from the adapter, runs z-score anomaly
        detection via the prevention client, and returns structured
        results. DEC-007: adapter provides data, intelligence here.
        
        Args:
            metric: Canonical metric to check
            asset_id: Target asset identifier
            threshold: Sensitivity in std deviations (default 2.0)
            
        Returns:
            AnomalyResult with detection findings
            
        Raises:
            AVAROSError: If prevention client is not configured.
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] check_anomaly: metric=%s, asset=%s, threshold=%s",
            query_id, metric.value, asset_id, threshold,
        )

        if self._prevention_client is None:
            raise AVAROSError(
                message="Anomaly detection requires a prevention client",
                code="ANOMALY_NOT_CONFIGURED",
                user_message=(
                    "Anomaly detection is not configured. "
                    "Please check the skill setup."
                ),
            )

        effective_threshold = (
            threshold
            if threshold is not None
            else self._get_anomaly_threshold()
        )
        result = self._run_pair_anomaly_check(
            metric=metric,
            asset_id=asset_id,
            threshold=effective_threshold,
            recommendation_id=query_id,
        )
        self._log_audit(
            "check_anomaly", query_id, metric.value, asset_id, result,
        )
        return result

    # Maximum number of concurrent HTTP requests during anomaly scans.
    _SCAN_CONCURRENCY = 10

    def scan_anomalies(
        self,
        metric: CanonicalMetric | None = None,
        asset_id: str | None = None,
        threshold: float | None = None,
    ) -> AnomalyScanResult:
        """Scan metric-asset pairs for anomalies using concurrent I/O.

        Only pairs with a configured ``metric_resource`` are checked,
        avoiding wasted calls on empty combinations.  All HTTP fetches
        run concurrently (capped by ``_SCAN_CONCURRENCY``) so a full
        scan completes in seconds rather than minutes.

        Args:
            metric: Optional metric filter. None scans all configured pairs.
            asset_id: Optional asset filter. None scans all discovered assets.
            threshold: Optional z-score threshold override.

        Returns:
            Aggregate anomaly scan result with counts and findings.
        """
        query_id = self._generate_query_id()
        effective_threshold = (
            threshold
            if threshold is not None
            else self._get_anomaly_threshold()
        )
        pairs = self._resolve_scan_pairs(metric=metric, asset_id=asset_id)

        logger.info(
            "[%s] scan_anomalies: %d pairs, threshold=%.2f",
            query_id, len(pairs), effective_threshold,
        )

        findings = self._run_async(
            self._scan_all_pairs_async(
                pairs, effective_threshold, query_id,
            ),
        )

        ordered = self._sort_scan_findings(findings)
        scan_result = AnomalyScanResult(
            checked_pairs=len(pairs),
            anomalous_pairs=len(ordered),
            findings=ordered,
            severity_counts=self._build_severity_counts(ordered),
            threshold=effective_threshold,
            recommendation_id=query_id,
        )
        self._log_audit(
            "scan_anomalies",
            query_id,
            "multiple",
            "multiple",
            scan_result,
        )
        return scan_result

    # ------------------------------------------------------------------
    # Concurrent scan internals
    # ------------------------------------------------------------------

    def _resolve_scan_pairs(
        self,
        metric: CanonicalMetric | None,
        asset_id: str | None,
    ) -> list[tuple[CanonicalMetric, str]]:
        """Build the list of (metric, asset_id) tuples to scan."""
        pairs = self._adapter.get_scannable_pairs()
        if not pairs:
            # Fallback: cross-product (legacy adapters without override)
            metrics = self._get_scan_metrics(metric=metric)
            asset_ids = self._get_scan_asset_ids(asset_id=asset_id)
            return [(m, a) for m in metrics for a in asset_ids]

        if metric is not None:
            pairs = [(m, a) for m, a in pairs if m == metric]
        if asset_id is not None:
            pairs = [(m, a) for m, a in pairs if a == asset_id]
        return pairs

    async def _scan_all_pairs_async(
        self,
        pairs: list[tuple[CanonicalMetric, str]],
        threshold: float,
        query_id: str,
    ) -> list[AnomalyResult]:
        """Check all pairs concurrently, return anomalous results."""
        semaphore = asyncio.Semaphore(self._SCAN_CONCURRENCY)

        async def _guarded(m: CanonicalMetric, a: str) -> AnomalyResult | None:
            async with semaphore:
                return await self._check_pair_async(
                    m, a, threshold, f"{query_id}:{m.value}:{a}",
                )

        results = await asyncio.gather(
            *(_guarded(m, a) for m, a in pairs),
            return_exceptions=True,
        )
        findings: list[AnomalyResult] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.debug("Pair scan error: %s", result)
                continue
            if result is not None and result.is_anomalous:
                findings.append(result)
        return findings

    # Days of historical data to collect for anomaly / drift analysis.
    # 30 days ensures enough data points even when APIs have gaps
    # (e.g. RENERYO only records weekdays).
    _ANOMALY_LOOKBACK_DAYS = 30
    _DRIFT_LOOKBACK_DAYS = 30
    _FORECAST_LOOKBACK_DAYS = 30

    async def _check_pair_async(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        threshold: float,
        recommendation_id: str,
    ) -> AnomalyResult | None:
        """Fully-async single-pair anomaly check."""
        if self._prevention_client is None:
            return None
        try:
            data_points = await self._collect_analysis_series_async(
                metric, asset_id, days=self._ANOMALY_LOOKBACK_DAYS,
            )
            detection = await self._prevention_client.detect_anomaly(
                metric, data_points, threshold, asset_id,
            )
            return self._build_anomaly_result(
                detection, metric, asset_id, recommendation_id,
            )
        except Exception as exc:
            logger.debug(
                "Anomaly check failed for %s/%s: %s",
                metric.value, asset_id, exc,
            )
            return None

    async def _collect_analysis_series_async(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        days: int = 7,
    ) -> list[DataPoint]:
        """Collect raw series first, then fall back to daily KPI snapshots."""
        now = datetime.now(timezone.utc)
        period = TimePeriod(
            start=now - timedelta(days=days),
            end=now,
            display_name="",
        )
        try:
            points = await self._adapter.get_raw_data(metric, asset_id, period)
            if len(points) >= 2:
                return sorted(points, key=lambda point: point.timestamp)
        except Exception as exc:
            logger.debug(
                "Raw series fallback for %s/%s: %s",
                metric.value,
                asset_id,
                exc,
            )

        return await self._collect_daily_series_async(metric, asset_id, days)

    async def _collect_daily_series_async(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        days: int = 7,
    ) -> list[DataPoint]:
        """Fetch daily KPI snapshots concurrently."""
        now = datetime.now(timezone.utc)

        async def _fetch_day(i: int) -> DataPoint | None:
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            day_end = day_start.replace(hour=23, minute=59, second=59)
            period = TimePeriod(
                start=day_start, end=day_end, display_name="",
            )
            try:
                result = await self._adapter.get_kpi(
                    metric, asset_id, period,
                )
                return DataPoint(
                    timestamp=day_start, value=result.value, unit=result.unit,
                )
            except Exception as exc:
                logger.debug(
                    "Skipping day %s for %s: %s",
                    day_start.date(), metric.value, exc,
                )
                return None

        results = await asyncio.gather(
            *(_fetch_day(i) for i in range(days, 0, -1)),
        )
        return [pt for pt in results if pt is not None]

    def _run_pair_anomaly_check(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        threshold: float,
        recommendation_id: str,
    ) -> AnomalyResult:
        """Run anomaly detection for one metric-asset pair."""
        if self._prevention_client is None:
            raise AVAROSError(
                message="Anomaly detection requires a prevention client",
                code="ANOMALY_NOT_CONFIGURED",
                user_message=(
                    "Anomaly detection is not configured. "
                    "Please check the skill setup."
                ),
            )

        data_points = self._collect_analysis_series(
            metric, asset_id, days=self._ANOMALY_LOOKBACK_DAYS,
        )
        detection = self._run_async(
            self._prevention_client.detect_anomaly(
                metric,
                data_points,
                threshold,
                asset_id,
            ),
        )
        return self._build_anomaly_result(
            detection,
            metric,
            asset_id,
            recommendation_id,
        )

    def _get_scan_metrics(
        self,
        metric: CanonicalMetric | None = None,
    ) -> list[CanonicalMetric]:
        """Return supported metrics for anomaly scanning."""
        if metric is not None:
            return [metric]

        try:
            metrics = self._adapter.get_supported_metrics()
        except Exception as exc:
            logger.warning("Could not load supported metrics: %s", exc)
            return []
        return metrics if isinstance(metrics, list) else []

    def _get_scan_asset_ids(self, asset_id: str | None = None) -> list[str]:
        """Return discovered asset IDs for anomaly scanning."""
        if asset_id:
            return [asset_id]

        try:
            assets = self._run_async(self._adapter.list_assets())
        except Exception as exc:
            logger.warning("Could not list assets for scan: %s", exc)
            return []
        return [
            getattr(asset, "asset_id", "")
            for asset in assets
            if str(getattr(asset, "asset_id", "")).strip()
        ]

    @staticmethod
    def _sort_scan_findings(
        findings: list[AnomalyResult],
    ) -> list[AnomalyResult]:
        """Sort findings by severity, then by absolute deviation."""
        severity_order = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
            "none": 0,
        }

        def _key(result: AnomalyResult) -> tuple[int, float]:
            deviation = abs(result.anomalies[0].deviation) if result.anomalies else 0.0
            return severity_order.get(result.severity, 0), deviation

        return sorted(findings, key=_key, reverse=True)

    @staticmethod
    def _build_severity_counts(
        findings: list[AnomalyResult],
    ) -> dict[str, int]:
        """Build severity distribution from anomaly findings."""
        counts = Counter(result.severity for result in findings)
        return dict(sorted(counts.items()))

    def _collect_analysis_series(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        days: int = 7,
    ) -> list[DataPoint]:
        """Collect raw series first, then fall back to daily KPI snapshots."""
        now = datetime.now(timezone.utc)
        period = TimePeriod(
            start=now - timedelta(days=days),
            end=now,
            display_name="",
        )
        try:
            points = self._run_async(
                self._adapter.get_raw_data(metric, asset_id, period),
            )
            if len(points) >= 2:
                return sorted(points, key=lambda point: point.timestamp)
        except Exception as exc:
            logger.debug(
                "Raw series fallback for %s/%s: %s",
                metric.value,
                asset_id,
                exc,
            )

        return self._collect_daily_series(metric, asset_id, days)

    def _collect_daily_series(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        days: int = 7,
    ) -> list[DataPoint]:
        """Build time-series by collecting daily KPI snapshots.

        Many APIs return single aggregate values per period rather
        than native time-series. This method constructs a time series
        by querying each day individually.

        Args:
            metric: Canonical metric to collect.
            asset_id: Target asset identifier.
            days: Number of past days to query.

        Returns:
            List of DataPoint sorted oldest-first.
        """
        now = datetime.now(timezone.utc)
        points: list[DataPoint] = []
        for i in range(days, 0, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            day_end = day_start.replace(
                hour=23, minute=59, second=59,
            )
            period = TimePeriod(
                start=day_start, end=day_end, display_name="",
            )
            try:
                result = self._run_async(
                    self._adapter.get_kpi(metric, asset_id, period),
                )
                points.append(DataPoint(
                    timestamp=day_start,
                    value=result.value,
                    unit=result.unit,
                ))
            except Exception as exc:
                logger.debug(
                    "Skipping day %s for %s: %s",
                    day_start.date(), metric.value, exc,
                )
        return points

    def _build_anomaly_result(
        self,
        detection: AnomalyDetectionResult,
        metric: CanonicalMetric,
        asset_id: str,
        query_id: str,
    ) -> AnomalyResult:
        """Convert AnomalyDetectionResult to AnomalyResult."""
        anomalies: list[Anomaly] = []
        if detection.is_anomalous:
            anomalies.append(Anomaly(
                timestamp=datetime.fromisoformat(detection.detected_at),
                metric=metric,
                expected_value=detection.expected_value or 0.0,
                actual_value=detection.actual_value or 0.0,
                deviation=detection.deviation,
                anomaly_type=detection.anomaly_type or "",
                description=detection.description,
            ))
        return AnomalyResult(
            is_anomalous=detection.is_anomalous,
            anomalies=anomalies,
            severity=detection.severity,
            asset_id=asset_id,
            metric=metric,
            recommendation_id=query_id,
            recommended_action=detection.recommended_action,
        )

    def check_drift(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        periods: int = 30,
    ) -> DriftReport:
        """
        Check a metric for gradual drift using linear regression.
        
        Fetches raw data from the adapter, runs drift analysis
        via the prevention client, and returns a DriftReport.
        
        Args:
            metric: Canonical metric to monitor
            asset_id: Target asset identifier
            periods: Number of periods to analyze
            
        Returns:
            DriftReport with drift analysis findings
            
        Raises:
            AVAROSError: If prevention client is not configured.
        """
        query_id = self._generate_query_id()
        
        logger.info(
            "[%s] check_drift: metric=%s, asset=%s, periods=%d",
            query_id, metric.value, asset_id, periods,
        )

        if self._prevention_client is None:
            raise AVAROSError(
                message="Drift monitoring requires a prevention client",
                code="DRIFT_NOT_CONFIGURED",
                user_message=(
                    "Drift monitoring is not configured. "
                    "Please check the skill setup."
                ),
            )

        data_points = self._collect_analysis_series(
            metric, asset_id, days=self._DRIFT_LOOKBACK_DAYS,
        )
        result = self._run_async(
            self._prevention_client.check_drift(
                metric,
                data_points,
                periods,
                asset_id=asset_id,
            ),
        )
        self._log_audit(
            "check_drift", query_id, metric.value, asset_id, result,
        )
        return result

    def forecast_metric(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        horizon_periods: int = 7,
    ) -> ForecastReport:
        """Forecast a KPI using configured PREVENTION predictive analytics."""
        query_id = self._generate_query_id()

        logger.info(
            "[%s] forecast_metric: metric=%s, asset=%s, horizon=%d",
            query_id, metric.value, asset_id, horizon_periods,
        )

        if self._prevention_client is None:
            raise AVAROSError(
                message="Forecasting requires a prevention client",
                code="FORECAST_NOT_CONFIGURED",
                user_message=(
                    "Forecasting is not configured. "
                    "Please check the PREVENTION setup."
                ),
            )

        data_points = self._collect_analysis_series(
            metric, asset_id, days=self._FORECAST_LOOKBACK_DAYS,
        )
        result = self._run_async(
            self._prevention_client.forecast_metric(
                metric,
                data_points,
                horizon_periods,
                asset_id=asset_id,
            ),
        )
        self._log_audit(
            "forecast_metric", query_id, metric.value, asset_id, result,
        )
        return result
    
    # =========================================================================
    # Query Type 5: What-If Simulation (INTELLIGENCE - Phase 3)
    # =========================================================================
    
    def simulate_whatif(
        self,
        scenario: WhatIfScenario,
    ) -> WhatIfResult:
        """Run a bounded decision-support what-if scenario.

        This is intentionally not a causal optimizer. It takes a live KPI
        baseline from the active adapter and applies the operator-stated
        scenario change to show the projected KPI value. The output is safe
        for proposal-level what-if exploration because assumptions stay
        explicit and no hidden model is claimed.
        """
        query_id = self._generate_query_id()

        logger.info(
            "[%s] simulate_whatif: scenario=%s, asset=%s, target=%s",
            query_id, scenario.name, scenario.asset_id, scenario.target_metric.value,
        )

        if not scenario.parameters:
            raise AVAROSError(
                message="What-if scenario has no parameter changes",
                code="WHATIF_INVALID_SCENARIO",
                user_message=(
                    "I need a specific what-if change, for example "
                    "'what if scrap rate improves by 5 percent'."
                ),
            )

        baseline = self.get_kpi(
            metric=scenario.target_metric,
            asset_id=scenario.asset_id,
            period=TimePeriod.today(),
        )
        change_percent = self._scenario_change_percent(scenario.parameters)
        projected = max(0.0, baseline.value * (1 + change_percent / 100.0))
        delta = projected - baseline.value
        delta_percent = (
            (delta / baseline.value) * 100.0
            if baseline.value
            else change_percent
        )
        confidence = self._whatif_confidence(scenario.parameters)
        factors = {
            parameter.name: self._parameter_change_percent(parameter)
            for parameter in scenario.parameters
        }

        result = WhatIfResult(
            scenario_name=scenario.name,
            target_metric=scenario.target_metric,
            baseline=round(baseline.value, 6),
            projected=round(projected, 6),
            delta=round(delta, 6),
            delta_percent=round(delta_percent, 4),
            confidence=confidence,
            factors=factors,
            unit=baseline.unit or scenario.target_metric.default_unit,
            recommendation_id=f"whatif-{query_id}",
        )
        self._log_audit(
            "simulate_whatif",
            query_id,
            scenario.target_metric.value,
            scenario.asset_id,
            result,
        )
        return result

    @staticmethod
    def _parameter_change_percent(parameter: ScenarioParameter) -> float:
        """Resolve a scenario parameter as a percentage change."""
        if parameter.unit.strip() == "%" and parameter.baseline_value == 0:
            return parameter.proposed_value
        return parameter.delta_percent

    @classmethod
    def _scenario_change_percent(
        cls,
        parameters: tuple[ScenarioParameter, ...],
    ) -> float:
        """Combine scenario parameters into one bounded percentage change."""
        combined = sum(cls._parameter_change_percent(param) for param in parameters)
        return max(-95.0, min(300.0, combined))

    @classmethod
    def _whatif_confidence(
        cls,
        parameters: tuple[ScenarioParameter, ...],
    ) -> float:
        """Confidence reflects small transparent assumptions, not model proof."""
        max_abs_change = max(
            abs(cls._parameter_change_percent(param))
            for param in parameters
        )
        if max_abs_change <= 10:
            return 0.65
        if max_abs_change <= 25:
            return 0.55
        return 0.45
    
    # =========================================================================
    # CO₂ Derivation (DEC-007, DEC-023)
    # =========================================================================

    def _is_derived_carbon_metric(
        self, metric: CanonicalMetric,
    ) -> bool:
        """True if metric is carbon and adapter lacks native support."""
        return (
            metric in self._DERIVED_CARBON_METRICS
            and not self._adapter.supports_capability("native_carbon")
        )

    def _derive_carbon_kpi(
        self, metric: CanonicalMetric,
        asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Derive carbon KPI from energy data + emission factors."""
        energy_source = self._resolve_energy_source()
        if metric == CanonicalMetric.CO2_TOTAL:
            energy = self._run_async(
                self._adapter.get_kpi(
                    CanonicalMetric.ENERGY_TOTAL, asset_id, period,
                ),
            )
            return self._co2_service.derive_co2_total(
                energy_kwh=energy.value,
                energy_source=energy_source,
                asset_id=asset_id, period=period,
            )
        if metric == CanonicalMetric.CO2_PER_UNIT:
            return self._derive_co2_per_unit(asset_id, period)
        raise MetricNotSupportedError(
            message=(
                f"{metric.value} requires production count data "
                f"(supplementary data not available)"
            ),
            metric=metric.value,
            platform=self._adapter.platform_name,
        )

    def _get_validated_summary(
        self,
        asset_id: str,
        period: TimePeriod,
        metric: CanonicalMetric,
    ) -> ProductionSummary:
        """Get production summary, raising if no data.

        Args:
            asset_id: Target asset.
            period: Time period.
            metric: Metric being derived (for error context).

        Returns:
            ProductionSummary with non-zero total_produced.

        Raises:
            MetricNotSupportedError: If total_produced is 0.
        """
        summary = self._production_service.get_production_summary(
            asset_id=asset_id,
            start_date=period.start.date(),
            end_date=period.end.date(),
        )
        if summary.total_produced == 0:
            raise MetricNotSupportedError(
                message="No production data for this period",
                metric=metric.value,
                platform=self._adapter.platform_name,
            )
        return summary

    def _ensure_metric_supported_for_asset(
        self,
        metric: CanonicalMetric,
        asset_id: str,
    ) -> None:
        """Raise a clear unsupported-metric error for energy-only meters."""
        if metric is not CanonicalMetric.ENERGY_PER_UNIT:
            return
        if not self._is_energy_total_only_asset(asset_id):
            return

        display_name = self._asset_display_name(asset_id)
        raise MetricNotSupportedError(
            message=(
                f"Metric '{metric.value}' requires production data for asset '{asset_id}'"
            ),
            metric=metric.value,
            platform=self._adapter.platform_name,
            available_metrics=[CanonicalMetric.ENERGY_TOTAL.value],
            user_message=(
                f"Energy per unit is not available for {display_name}. "
                "This meter only exposes total energy, and energy per unit requires production data."
            ),
        )

    def _is_energy_total_only_asset(self, asset_id: str) -> bool:
        """Return True when asset metadata indicates cumulative energy only."""
        mapping = self._resolve_asset_mapping(asset_id)
        if not isinstance(mapping, dict):
            return False

        capability_mode = str(mapping.get("capability_mode", "")).strip().lower()
        if capability_mode == "energy_only":
            return True
        if capability_mode:
            return self._metric_resource_metric_names(mapping) == ("energy_total",)

        return (
            self._native_bound_metric_names(mapping) == ("energy_total",)
            or self._metric_resource_metric_names(mapping) == ("energy_total",)
        )

    def _resolve_asset_mapping(self, asset_id: str) -> dict[str, object] | None:
        """Resolve asset mapping by id, display name, or alias."""
        if self._settings_service is None:
            return None
        try:
            mappings = self._settings_service.get_asset_mappings()
        except Exception:
            logger.debug("Asset mapping lookup failed", exc_info=True)
            return None
        if not isinstance(mappings, dict):
            return None

        direct = mappings.get(asset_id)
        if isinstance(direct, dict):
            return direct
        target = self._normalize_asset_lookup(asset_id)
        if not target:
            return None

        for key, raw_mapping in mappings.items():
            if not isinstance(raw_mapping, dict):
                continue
            if self._mapping_matches_asset(target, str(key), raw_mapping):
                return raw_mapping
        return None

    def _asset_display_name(self, asset_id: str) -> str:
        """Return a user-facing asset label when metadata is available."""
        mapping = self._resolve_asset_mapping(asset_id)
        if not isinstance(mapping, dict):
            return asset_id
        display_name = str(mapping.get("display_name", "")).strip()
        return display_name or asset_id

    @staticmethod
    def _native_bound_metric_names(mapping: dict[str, object]) -> tuple[str, ...]:
        """Return normalized native metric binding names for an asset mapping."""
        native_bindings = mapping.get("native_metric_bindings")
        if not isinstance(native_bindings, dict):
            return ()
        return tuple(sorted(str(key).strip() for key in native_bindings if str(key).strip()))

    @staticmethod
    def _metric_resource_metric_names(mapping: dict[str, object]) -> tuple[str, ...]:
        """Return normalized metric-resource names for an asset mapping."""
        metric_resources = mapping.get("metric_resources")
        if not isinstance(metric_resources, dict):
            return ()
        return tuple(
            sorted(
                str(key).strip()
                for key, value in metric_resources.items()
                if str(key).strip() and str(value).strip()
            ),
        )

    @staticmethod
    def _mapping_matches_asset(
        target: str,
        key: str,
        mapping: dict[str, object],
    ) -> bool:
        """Return True when an asset mapping row matches normalized lookup text."""
        candidates = [key, str(mapping.get("display_name", ""))]
        aliases = mapping.get("aliases")
        if isinstance(aliases, list):
            candidates.extend(str(alias) for alias in aliases)
        return any(
            QueryDispatcher._normalize_asset_lookup(candidate) == target
            for candidate in candidates
            if candidate
        )

    @staticmethod
    def _normalize_asset_lookup(value: str) -> str:
        """Normalize asset identifiers for tolerant comparisons."""
        return re.sub(r"[^a-z0-9]", "", value.lower().strip())

    def _derive_co2_per_unit(
        self, asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Derive co2_per_unit from energy + production data.

        Raises:
            MetricNotSupportedError: If no production service or no data.
        """
        if self._production_service is None:
            raise MetricNotSupportedError(
                message="co2_per_unit requires production data service",
                metric=CanonicalMetric.CO2_PER_UNIT.value,
                platform=self._adapter.platform_name,
            )
        energy = self._run_async(
            self._adapter.get_kpi(
                CanonicalMetric.ENERGY_TOTAL, asset_id, period,
            ),
        )
        summary = self._get_validated_summary(
            asset_id, period, CanonicalMetric.CO2_PER_UNIT,
        )
        return self._co2_service.derive_co2_per_unit(
            energy_kwh=energy.value,
            production_count=summary.total_produced,
            energy_source=self._resolve_energy_source(),
            asset_id=asset_id, period=period,
        )

    def _derive_carbon_trend(
        self, metric: CanonicalMetric, asset_id: str,
        period: TimePeriod, granularity: str,
    ) -> TrendResult:
        """Derive carbon trend from energy trend data."""
        if metric != CanonicalMetric.CO2_TOTAL:
            raise MetricNotSupportedError(
                message=(
                    f"Trend for {metric.value} requires production "
                    f"count data (not yet available)"
                ),
                metric=metric.value,
                platform=self._adapter.platform_name,
            )
        energy_trend = self._run_async(
            self._adapter.get_trend(
                CanonicalMetric.ENERGY_TOTAL, asset_id,
                period, granularity,
            ),
        )
        return self._co2_service.derive_co2_trend(
            energy_data_points=energy_trend.data_points,
            energy_source=self._resolve_energy_source(),
            asset_id=asset_id, period=period,
            granularity=granularity,
        )

    # =========================================================================
    # Supplementary Data Derivation (DEC-023)
    # =========================================================================

    def _is_derived_supplementary_metric(
        self, metric: CanonicalMetric,
    ) -> bool:
        """True if metric needs supplementary production data."""
        return (
            metric in self._DERIVED_SUPPLEMENTARY_METRICS
            and self._production_service is not None
            and not self._adapter.supports_capability(
                "native_" + metric.value,
            )
        )

    def _resolve_energy_source(self) -> str:
        """Return the configured energy source for CO2 derivation."""
        if self._settings_service is None:
            return "electricity"
        try:
            return self._settings_service.get_primary_energy_source()
        except Exception:
            logger.debug("Energy source lookup failed; using electricity", exc_info=True)
            return "electricity"

    def _get_anomaly_threshold(self) -> float:
        """Return conversational anomaly threshold (DEC-006).

        Falls back to 2.0 when no SettingsService is available.

        Returns:
            Configured threshold or 2.0 default.
        """
        if self._settings_service is None:
            return 2.0
        try:
            return self._settings_service.get_query_anomaly_threshold()
        except Exception:
            logger.debug("Anomaly threshold lookup failed; using 2.0", exc_info=True)
            return 2.0

    def _derive_supplementary_kpi(
        self, metric: CanonicalMetric,
        asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Derive KPI from supplementary production data.

        Args:
            metric: ENERGY_PER_UNIT or MATERIAL_EFFICIENCY.
            asset_id: Target asset.
            period: Time period.

        Returns:
            KPIResult with derived value.

        Raises:
            MetricNotSupportedError: If no production data for period.
        """
        if metric == CanonicalMetric.ENERGY_PER_UNIT:
            return self._derive_energy_per_unit(asset_id, period)
        if metric == CanonicalMetric.MATERIAL_EFFICIENCY:
            return self._derive_material_efficiency(asset_id, period)
        raise MetricNotSupportedError(
            message=f"Cannot derive {metric.value} from supplementary data",
            metric=metric.value,
            platform=self._adapter.platform_name,
        )

    def _derive_energy_per_unit(
        self, asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Derive energy_per_unit = energy_total / production_count.

        Raises:
            MetricNotSupportedError: If no production data.
        """
        energy = self._run_async(
            self._adapter.get_kpi(
                CanonicalMetric.ENERGY_TOTAL, asset_id, period,
            ),
        )
        summary = self._get_validated_summary(
            asset_id, period, CanonicalMetric.ENERGY_PER_UNIT,
        )
        value = round(energy.value / summary.total_produced, 4)
        return KPIResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            value=value,
            unit="kWh/unit",
            asset_id=asset_id,
            period=period,
            timestamp=datetime.utcnow(),
        )

    def _derive_material_efficiency(
        self, asset_id: str, period: TimePeriod,
    ) -> KPIResult:
        """Derive material_efficiency from supplementary data only.

        Raises:
            MetricNotSupportedError: If no production data.
        """
        summary = self._get_validated_summary(
            asset_id, period, CanonicalMetric.MATERIAL_EFFICIENCY,
        )
        return KPIResult(
            metric=CanonicalMetric.MATERIAL_EFFICIENCY,
            value=summary.material_efficiency,
            unit="%",
            asset_id=asset_id,
            period=period,
            timestamp=datetime.utcnow(),
        )

    # =========================================================================
    # Async/Sync Bridging
    # =========================================================================
    
    def _run_async(self, coro):
        """
        Run an async coroutine synchronously.
        
        Creates a new event loop if needed. This bridges the sync OVOS
        handler world with async adapter calls.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Result of the coroutine
        """
        def _runner():
            # Keep one dedicated event loop per dispatcher so aiohttp session
            # is always used on the same loop/thread.
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            return self._loop.run_until_complete(coro)

        future = self._executor.submit(_runner)
        return future.result(timeout=60)

    def shutdown(self) -> None:
        """Shutdown adapter and dispatcher async resources cleanly."""
        try:
            self._run_async(self._adapter.shutdown())
        except Exception as exc:
            logger.warning("Adapter shutdown during dispatcher.stop failed: %s", exc)

        def _close_loop() -> None:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.close()

        try:
            self._executor.submit(_close_loop).result(timeout=10)
        except Exception as exc:
            logger.warning("Dispatcher event loop close failed: %s", exc)
        finally:
            self._executor.shutdown(wait=True, cancel_futures=True)
    
    # =========================================================================
    # Audit Logging (GDPR Compliance)
    # =========================================================================
    
    def _log_audit(
        self,
        query_type: str,
        query_id: str,
        metric: str,
        asset_id: str,
        result,
        user_role: str = "operator",
    ) -> None:
        """
        Log query for audit trail (GDPR compliance).
        
        Creates immutable audit record with:
        - Query ID for traceability
        - Query type and parameters
        - Result summary (not full data)
        - Timestamp
        
        Args:
            query_type: Type of query (get_kpi, compare, etc.)
            query_id: Unique query identifier
            metric: Canonical metric name
            asset_id: Asset identifier
            result: Query result object
            user_role: User role for access control
        """
        recommendation_id = getattr(result, 'recommendation_id', None)
        
        # Generate response summary based on result type
        response_summary = self._generate_response_summary(result)
        
        # Log to audit service
        try:
            self._audit_logger.log_query(
                query_id=query_id,
                user_role=user_role,
                query_type=query_type,
                metric=metric,
                asset_id=asset_id,
                recommendation_id=recommendation_id,
                response_summary=response_summary,
            )
        except Exception as e:
            # Don't fail query if audit logging fails
            logger.error("Failed to write audit log: %s", e)
    
    def _generate_response_summary(self, result) -> str:
        """Generate brief summary of result for audit log."""
        from skill.domain.anomaly_models import DriftReport
        from skill.domain.results import (
            KPIResult, ComparisonResult, TrendResult,
            AnomalyResult, AnomalyScanResult, WhatIfResult
        )
        
        if isinstance(result, KPIResult):
            return f"KPI value: {result.value:.2f} {result.unit}"
        elif isinstance(result, ComparisonResult):
            return f"Winner: {result.winner_id}, diff: {result.difference:.2f}"
        elif isinstance(result, TrendResult):
            return f"Direction: {result.direction}, change: {result.change_percent:.1f}%"
        elif isinstance(result, AnomalyResult):
            return f"Anomalous: {result.is_anomalous}, count: {len(result.anomalies)}"
        elif isinstance(result, AnomalyScanResult):
            return (
                f"Scan anomalies: {result.anomalous_pairs}/"
                f"{result.checked_pairs}"
            )
        elif isinstance(result, DriftReport):
            return f"Drift: {result.has_drift}, direction: {result.drift_direction}"
        elif isinstance(result, AVAROSError):
            return result.user_message
        elif isinstance(result, WhatIfResult):
            return f"Delta: {result.delta:.2f}, improvement: {result.is_improvement}"
        else:
            return str(type(result).__name__)

    
    def _generate_query_id(self) -> str:
        """Generate unique query ID for tracing."""
        return f"q-{uuid.uuid4().hex[:8]}"
