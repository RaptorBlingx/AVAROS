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
                energy_source=self._resolve_energy_source(),
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

    def _resolve_energy_source(self) -> str:
        """Return the configured energy source for collector-side CO2 math."""
        try:
            return self._settings.get_primary_energy_source()
        except Exception:
            logger.debug("Collector energy source lookup failed", exc_info=True)
            return "electricity"
