"""KPI data collector — fetches metrics from the active adapter and records
baselines / snapshots in the KPI measurement database.

Works with both real and mock platforms. For mock mode, values are
slightly biased to produce realistic movement on KPI cards.
"""

from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.factory import AdapterFactory
from skill.domain.kpi_baseline import KPIBaseline, KPISnapshot
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult
from skill.services.co2_service import CO2DerivationService
from skill.services.kpi_measurement import KPIMeasurementService
from skill.services.production_data import ProductionDataService
from skill.services.settings import SettingsService

logger = logging.getLogger(__name__)

_KPI_METRICS: Sequence[CanonicalMetric] = (
    CanonicalMetric.ENERGY_PER_UNIT,
    CanonicalMetric.MATERIAL_EFFICIENCY,
    CanonicalMetric.CO2_TOTAL,
)

_DEFAULT_ASSET_ID = "*"


class KPICollector:
    """Pulls KPI values from the active manufacturing adapter and persists
    them via :class:`KPIMeasurementService`.

    Args:
        settings_service: Provides platform configuration (type, URL, key).
        kpi_service: Handles baseline/snapshot DB operations.
    """

    def __init__(
        self,
        settings_service: SettingsService,
        kpi_service: KPIMeasurementService,
        production_service: ProductionDataService | None = None,
    ) -> None:
        self._settings = settings_service
        self._kpi = kpi_service
        self._production = production_service or ProductionDataService()
        self._co2 = CO2DerivationService(settings_service)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def seed_baselines(self, site_id: str) -> int:
        """Record initial baselines for any metrics that lack one.

        Returns the number of baselines written (0 when all already exist).
        """
        existing = self._kpi.get_all_baselines(site_id)
        existing_metrics = {bl.metric for bl in existing}

        missing = [m for m in _KPI_METRICS if m.value not in existing_metrics]
        if not missing:
            logger.info("All baselines present for site %s", site_id)
            return 0

        adapter = await self._create_adapter()
        try:
            return await self._fetch_and_record_baselines(
                adapter, site_id, missing,
            )
        finally:
            await adapter.shutdown()

    async def collect_snapshots(self, site_id: str) -> int:
        """Fetch current metric values and record them as snapshots.

        Returns the number of snapshots recorded.
        """
        adapter = await self._create_adapter()
        try:
            return await self._fetch_and_record_snapshots(adapter, site_id)
        finally:
            await adapter.shutdown()

    async def seed_mock_snapshot_history(self, site_id: str, points: int = 10) -> int:
        """Generate historical snapshot points for mock trends.

        This backfills time-series data so charts are informative immediately
        after switching to the mock profile.
        """
        if not self._is_mock_platform():
            return 0

        period = TimePeriod.last_month()
        now = datetime.now(tz=timezone.utc)
        adapter = await self._create_adapter()
        recorded = 0
        try:
            baseline_map = {
                metric.value: self._kpi.get_baseline(metric.value, site_id)
                for metric in _KPI_METRICS
            }
            for idx in range(points):
                measured_at = now - timedelta(days=(points - 1 - idx) * 3)
                cache: dict[CanonicalMetric, KPIResult] = {}
                for metric in _KPI_METRICS:
                    result = await self._resolve_metric_result(
                        adapter=adapter,
                        metric=metric,
                        period=period,
                        cache=cache,
                    )
                    if result is None:
                        continue
                    baseline = baseline_map.get(metric.value)
                    if baseline is not None:
                        end_value = self._mock_snapshot_from_baseline(
                            metric=metric,
                            baseline_value=baseline.baseline_value,
                        )
                        progress_ratio = (idx + 1) / points
                        snapshot_value = round(
                            baseline.baseline_value
                            + (end_value - baseline.baseline_value) * progress_ratio,
                            4,
                        )
                    else:
                        snapshot_value = self._apply_mock_bias(
                            metric=metric,
                            value=result.value,
                            phase="snapshot",
                            enabled=True,
                        )
                    self._kpi.record_snapshot(
                        KPISnapshot(
                            metric=metric.value,
                            site_id=site_id,
                            value=snapshot_value,
                            unit=result.unit,
                            measured_at=measured_at,
                            period_start=period.start.date(),
                            period_end=period.end.date(),
                        )
                    )
                    recorded += 1
        finally:
            await adapter.shutdown()
        return recorded

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_adapter(self) -> ManufacturingAdapter:
        factory = AdapterFactory(self._settings)
        return await factory.create_async()

    async def _fetch_and_record_baselines(
        self,
        adapter: ManufacturingAdapter,
        site_id: str,
        metrics: Sequence[CanonicalMetric],
    ) -> int:
        period = TimePeriod.last_month()
        now = datetime.now(tz=timezone.utc)
        recorded = 0
        is_mock = self._is_mock_platform()

        cache: dict[CanonicalMetric, KPIResult] = {}
        for metric in metrics:
            try:
                result = await self._resolve_metric_result(
                    adapter=adapter,
                    metric=metric,
                    period=period,
                    cache=cache,
                )
                if result is None:
                    logger.info(
                        "Baseline skipped for %s (no usable source data)",
                        metric.value,
                    )
                    continue
                baseline_value = self._apply_mock_bias(
                    metric=metric,
                    value=result.value,
                    phase="baseline",
                    enabled=is_mock,
                )
                baseline = KPIBaseline(
                    metric=metric.value,
                    site_id=site_id,
                    baseline_value=baseline_value,
                    unit=result.unit,
                    recorded_at=now,
                    period_start=period.start.date(),
                    period_end=period.end.date(),
                    notes="auto-seeded by KPICollector",
                )
                self._kpi.record_baseline(baseline)
                recorded += 1
                logger.info(
                    "Baseline seeded: %s = %.4f %s (site=%s)",
                    metric.value, baseline_value, result.unit, site_id,
                )
            except Exception:
                logger.exception("Failed to seed baseline for %s", metric.value)

        return recorded

    async def _fetch_and_record_snapshots(
        self,
        adapter: ManufacturingAdapter,
        site_id: str,
    ) -> int:
        period = TimePeriod.last_month()
        now = datetime.now(tz=timezone.utc)
        recorded = 0
        is_mock = self._is_mock_platform()

        cache: dict[CanonicalMetric, KPIResult] = {}
        for metric in _KPI_METRICS:
            try:
                result = await self._resolve_metric_result(
                    adapter=adapter,
                    metric=metric,
                    period=period,
                    cache=cache,
                )
                if result is None:
                    logger.info(
                        "Snapshot skipped for %s (no usable source data)",
                        metric.value,
                    )
                    continue
                snapshot_value = self._apply_mock_bias(
                    metric=metric,
                    value=result.value,
                    phase="snapshot",
                    enabled=is_mock,
                )
                if is_mock:
                    baseline = self._kpi.get_baseline(metric.value, site_id)
                    if baseline is not None:
                        snapshot_value = self._mock_snapshot_from_baseline(
                            metric=metric,
                            baseline_value=baseline.baseline_value,
                        )
                snapshot = KPISnapshot(
                    metric=metric.value,
                    site_id=site_id,
                    value=snapshot_value,
                    unit=result.unit,
                    measured_at=now,
                    period_start=period.start.date(),
                    period_end=period.end.date(),
                )
                self._kpi.record_snapshot(snapshot)
                recorded += 1
                logger.info(
                    "Snapshot recorded: %s = %.4f %s (site=%s)",
                    metric.value, snapshot_value, result.unit, site_id,
                )
            except Exception:
                logger.exception("Failed to record snapshot for %s", metric.value)

        return recorded

    async def _resolve_metric_result(
        self,
        adapter: ManufacturingAdapter,
        metric: CanonicalMetric,
        period: TimePeriod,
        cache: dict[CanonicalMetric, KPIResult],
    ) -> KPIResult | None:
        """Resolve metric value from adapter or derived sources.

        Resolution order:
        1) Direct adapter metric call
        2) Derived fallback for CO2 total (from energy total)
        3) Derived fallback for material efficiency (from production records)
        """
        if metric in cache:
            return cache[metric]

        try:
            direct = await adapter.get_kpi(metric, _DEFAULT_ASSET_ID, period)
            cache[metric] = direct
            return direct
        except Exception:
            logger.debug("Direct metric fetch failed for %s", metric.value, exc_info=True)

        if metric == CanonicalMetric.CO2_TOTAL:
            derived = await self._derive_co2_total(adapter, period, cache)
            if derived is not None:
                cache[metric] = derived
            return derived

        if metric == CanonicalMetric.MATERIAL_EFFICIENCY:
            derived = self._derive_material_efficiency(period)
            if derived is not None:
                cache[metric] = derived
            return derived

        return None

    async def _derive_co2_total(
        self,
        adapter: ManufacturingAdapter,
        period: TimePeriod,
        cache: dict[CanonicalMetric, KPIResult],
    ) -> KPIResult | None:
        """Derive CO2 total using energy_total and configured factor."""
        energy_total = cache.get(CanonicalMetric.ENERGY_TOTAL)
        if energy_total is None:
            try:
                energy_total = await adapter.get_kpi(
                    CanonicalMetric.ENERGY_TOTAL,
                    _DEFAULT_ASSET_ID,
                    period,
                )
                cache[CanonicalMetric.ENERGY_TOTAL] = energy_total
            except Exception:
                logger.debug("Energy total unavailable for co2 derivation", exc_info=True)
                return None

        try:
            return self._co2.derive_co2_total(
                energy_kwh=energy_total.value,
                energy_source="electricity",
                asset_id=_DEFAULT_ASSET_ID,
                period=period,
            )
        except Exception:
            logger.debug("CO2 derivation failed", exc_info=True)
            return None

    def _derive_material_efficiency(self, period: TimePeriod) -> KPIResult | None:
        """Derive material efficiency from production records, if present."""
        records = self._production.get_records(
            start_date=period.start.date(),
            end_date=period.end.date(),
        )
        total_produced = sum(r.production_count for r in records)
        if total_produced <= 0:
            return None

        total_good = sum(r.good_count for r in records)
        efficiency = round((total_good / total_produced) * 100.0, 1)
        return KPIResult(
            metric=CanonicalMetric.MATERIAL_EFFICIENCY,
            value=efficiency,
            unit="%",
            asset_id=_DEFAULT_ASSET_ID,
            period=period,
            timestamp=datetime.now(tz=timezone.utc),
        )

    def _is_mock_platform(self) -> bool:
        config = self._settings.get_platform_config()
        platform = getattr(config, "platform_type", "mock") or "mock"
        return platform.lower() == "mock"

    @staticmethod
    def _apply_mock_bias(
        metric: CanonicalMetric,
        value: float,
        phase: str,
        enabled: bool,
    ) -> float:
        """Bias mock values so cards are dynamic and not always red."""
        if not enabled:
            return value

        if metric in (CanonicalMetric.ENERGY_PER_UNIT, CanonicalMetric.CO2_TOTAL):
            if metric == CanonicalMetric.ENERGY_PER_UNIT:
                # Keep energy mostly "on track" in mock demo.
                if phase == "baseline":
                    return round(value * random.uniform(1.06, 1.10), 4)
                return round(value * random.uniform(0.89, 0.94), 4)

            # CO2 is usually mid-band (at risk / off-track) for variety.
            if phase == "baseline":
                return round(value * random.uniform(1.03, 1.07), 4)
            return round(value * random.uniform(0.97, 1.02), 4)

        if metric == CanonicalMetric.MATERIAL_EFFICIENCY:
            # Keep material around threshold so cards do not all share same tone.
            if phase == "baseline":
                return round(value * random.uniform(0.97, 0.995), 4)
            return round(value * random.uniform(0.995, 1.02), 4)

        return value

    @staticmethod
    def _mock_snapshot_from_baseline(
        metric: CanonicalMetric,
        baseline_value: float,
    ) -> float:
        """Deterministic mock bands to avoid extreme target attainment swings.

        Intended visual mix:
        - energy_per_unit: on track (around 10% improvement vs 8% target)
        - material_efficiency: at risk (around 3.5% improvement vs 5% target)
        - co2_total: off track (around -4% improvement for reduction KPI)
        """
        if metric == CanonicalMetric.ENERGY_PER_UNIT:
            return round(baseline_value * 0.90, 4)
        if metric == CanonicalMetric.MATERIAL_EFFICIENCY:
            return round(baseline_value * 1.035, 4)
        if metric == CanonicalMetric.CO2_TOTAL:
            return round(baseline_value * 1.04, 4)
        return baseline_value
