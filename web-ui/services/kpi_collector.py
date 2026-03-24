"""KPI data collector — fetches metrics from the active adapter and records
baselines / snapshots in the KPI measurement database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.factory import AdapterFactory
from skill.domain.kpi_baseline import KPIBaseline, KPISnapshot
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult, TrendResult
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
        if not self._settings.is_configured():
            return 0

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
        if not self._settings.is_configured():
            return 0

        adapter = await self._create_adapter()
        try:
            return await self._fetch_and_record_snapshots(adapter, site_id)
        finally:
            await adapter.shutdown()

    async def backfill_snapshots_from_trend(
        self,
        site_id: str,
        *,
        min_existing_points: int = 6,
    ) -> int:
        """Backfill historical snapshots from trend endpoints when history is sparse."""
        if not self._settings.is_configured():
            return 0

        adapter = await self._create_adapter()
        try:
            return await self._backfill_snapshots_from_trend_with_adapter(
                adapter=adapter,
                site_id=site_id,
                min_existing_points=min_existing_points,
            )
        finally:
            await adapter.shutdown()

    def realign_baselines_to_earliest_snapshot(self, site_id: str) -> int:
        """Align baseline values to earliest available snapshot per metric."""
        updated = 0
        baselines = self._kpi.get_all_baselines(site_id)
        for baseline in baselines:
            snapshots = self._kpi.get_snapshots(baseline.metric, site_id)
            if len(snapshots) < 2:
                continue
            earliest = snapshots[0]
            if (
                baseline.baseline_value == earliest.value
                and baseline.unit == earliest.unit
            ):
                continue
            aligned = KPIBaseline(
                metric=baseline.metric,
                site_id=site_id,
                baseline_value=earliest.value,
                unit=earliest.unit or baseline.unit,
                recorded_at=earliest.measured_at,
                period_start=earliest.period_start,
                period_end=earliest.period_end,
                notes="auto-aligned to earliest historical snapshot",
            )
            self._kpi.record_baseline(aligned)
            updated += 1
        return updated

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

        cache: dict[CanonicalMetric, KPIResult] = {}
        for metric in metrics:
            try:
                result = await self._resolve_baseline_result(
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
                baseline = KPIBaseline(
                    metric=metric.value,
                    site_id=site_id,
                    baseline_value=result.value,
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
                    metric.value, result.value, result.unit, site_id,
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
                snapshot = KPISnapshot(
                    metric=metric.value,
                    site_id=site_id,
                    value=result.value,
                    unit=result.unit,
                    measured_at=now,
                    period_start=period.start.date(),
                    period_end=period.end.date(),
                )
                self._kpi.record_snapshot(snapshot)
                recorded += 1
                logger.info(
                    "Snapshot recorded: %s = %.4f %s (site=%s)",
                    metric.value, result.value, result.unit, site_id,
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

        metric_asset_id = self._resolve_metric_asset_id(metric)
        try:
            direct = await adapter.get_kpi(metric, metric_asset_id, period)
            cache[metric] = direct
            return direct
        except Exception:
            logger.debug("Direct metric fetch failed for %s", metric.value, exc_info=True)

        if metric == CanonicalMetric.CO2_TOTAL:
            derived = await self._derive_co2_total(
                adapter,
                period,
                cache,
                asset_id=metric_asset_id,
            )
            if derived is not None:
                cache[metric] = derived
            return derived

        if metric == CanonicalMetric.MATERIAL_EFFICIENCY:
            derived = self._derive_material_efficiency(period)
            if derived is not None:
                cache[metric] = derived
            return derived

        return None

    async def _resolve_baseline_result(
        self,
        adapter: ManufacturingAdapter,
        metric: CanonicalMetric,
        period: TimePeriod,
        cache: dict[CanonicalMetric, KPIResult],
    ) -> KPIResult | None:
        """Resolve baseline value preferring the oldest trend point in period."""
        asset_id = self._resolve_metric_asset_id(metric)
        try:
            trend = await adapter.get_trend(
                metric=metric,
                asset_id=asset_id,
                period=period,
                granularity="daily",
            )
            if isinstance(trend, TrendResult) and trend.data_points:
                first_point = min(trend.data_points, key=lambda point: point.timestamp)
                return KPIResult(
                    metric=metric,
                    value=first_point.value,
                    unit=first_point.unit or metric.default_unit,
                    asset_id=asset_id,
                    period=period,
                    timestamp=self._normalize_measurement_time(first_point.timestamp),
                )
        except Exception:
            logger.debug(
                "Baseline trend lookup failed for %s, falling back to direct KPI",
                metric.value,
                exc_info=True,
            )

        return await self._resolve_metric_result(
            adapter=adapter,
            metric=metric,
            period=period,
            cache=cache,
        )

    async def _backfill_snapshots_from_trend_with_adapter(
        self,
        *,
        adapter: ManufacturingAdapter,
        site_id: str,
        min_existing_points: int,
    ) -> int:
        """Persist trend points as snapshots when period history is insufficient."""
        period = TimePeriod.last_month()
        recorded = 0
        for metric in _KPI_METRICS:
            existing = self._kpi.get_snapshots(
                metric=metric.value,
                site_id=site_id,
                start_date=period.start.date(),
                end_date=period.end.date(),
            )
            if len(existing) >= min_existing_points:
                continue

            asset_id = self._resolve_metric_asset_id(metric)
            try:
                trend = await adapter.get_trend(
                    metric=metric,
                    asset_id=asset_id,
                    period=period,
                    granularity="daily",
                )
            except Exception:
                logger.debug(
                    "Trend backfill failed for %s",
                    metric.value,
                    exc_info=True,
                )
                continue

            if not isinstance(trend, TrendResult) or not trend.data_points:
                continue

            existing_timestamps = {
                self._normalize_measurement_time(snapshot.measured_at)
                for snapshot in existing
            }
            for point in trend.data_points:
                measured_at = self._normalize_measurement_time(point.timestamp)
                if measured_at in existing_timestamps:
                    continue
                snapshot = KPISnapshot(
                    metric=metric.value,
                    site_id=site_id,
                    value=point.value,
                    unit=point.unit or metric.default_unit,
                    measured_at=measured_at,
                    period_start=trend.period.start.date(),
                    period_end=trend.period.end.date(),
                )
                self._kpi.record_snapshot(snapshot)
                existing_timestamps.add(measured_at)
                recorded += 1

        return recorded

    async def _derive_co2_total(
        self,
        adapter: ManufacturingAdapter,
        period: TimePeriod,
        cache: dict[CanonicalMetric, KPIResult],
        *,
        asset_id: str,
    ) -> KPIResult | None:
        """Derive CO2 total using energy_total and configured factor."""
        energy_total = cache.get(CanonicalMetric.ENERGY_TOTAL)
        if energy_total is None:
            try:
                energy_total = await adapter.get_kpi(
                    CanonicalMetric.ENERGY_TOTAL,
                    asset_id,
                    period,
                )
                cache[CanonicalMetric.ENERGY_TOTAL] = energy_total
            except Exception:
                logger.debug("Energy total unavailable for co2 derivation", exc_info=True)
                return None

        try:
            return self._co2.derive_co2_total(
                energy_kwh=energy_total.value,
                energy_source=self._resolve_energy_source(),
                asset_id=asset_id,
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

    def _resolve_energy_source(self) -> str:
        """Return the configured energy source for collector-side CO2 math."""
        try:
            return self._settings.get_primary_energy_source()
        except Exception:
            logger.debug("Collector energy source lookup failed", exc_info=True)
            return "electricity"

    def _resolve_metric_asset_id(self, metric: CanonicalMetric) -> str:
        """Choose a concrete asset for metrics backed by per-asset resources."""
        try:
            mappings = self._settings.get_asset_mappings()
        except Exception:
            logger.debug("Asset mapping lookup failed, using default asset", exc_info=True)
            return _DEFAULT_ASSET_ID

        if not isinstance(mappings, dict) or not mappings:
            return _DEFAULT_ASSET_ID

        metric_name = metric.value
        for asset_id, mapping in mappings.items():
            if not isinstance(mapping, dict):
                continue
            metric_resources = mapping.get("metric_resources", {})
            if not isinstance(metric_resources, dict):
                continue
            resource_id = str(metric_resources.get(metric_name, "")).strip()
            if resource_id:
                return str(asset_id)

        return _DEFAULT_ASSET_ID

    @staticmethod
    def _normalize_measurement_time(value: datetime) -> datetime:
        """Normalize timestamps to UTC-naive precision for DB consistency."""
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
        return value.replace(microsecond=0)
