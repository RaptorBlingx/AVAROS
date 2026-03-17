"""Deterministic test adapter that returns fixed values for all metrics.

Used in integration tests that previously relied on MockAdapter for
demo data. Every metric returns a known value so assertions are stable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from skill.adapters.base import ManufacturingAdapter
from skill.domain.models import (
    Asset,
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


_METRIC_VALUES: dict[str, tuple[float, str]] = {
    "energy_per_unit": (42.5, "kWh/unit"),
    "energy_total": (12500.0, "kWh"),
    "peak_demand": (185.0, "kW"),
    "peak_tariff_exposure": (23.5, "%"),
    "scrap_rate": (3.2, "%"),
    "rework_rate": (1.8, "%"),
    "material_efficiency": (96.5, "%"),
    "recycled_content": (35.0, "%"),
    "supplier_lead_time": (4.5, "days"),
    "supplier_defect_rate": (0.8, "%"),
    "supplier_on_time": (94.0, "%"),
    "supplier_co2_per_kg": (2.1, "kg CO₂/kg"),
    "oee": (85.0, "%"),
    "throughput": (120.0, "units/hr"),
    "cycle_time": (30.0, "sec"),
    "changeover_time": (15.0, "min"),
    "co2_per_unit": (8.5, "kg CO₂-eq/unit"),
    "co2_total": (2500.0, "kg CO₂-eq"),
    "co2_per_batch": (170.0, "kg CO₂-eq/batch"),
}

_DEMO_ASSETS = (
    "Line-1",
    "Line-2",
    "Assembly-A",
    "Assembly-B",
    "CNC-Mill-01",
    "Compressor-1",
    "Compressor-2",
    "Furnace-A",
    "Paint-Booth-1",
    "Conveyor-Main",
)

_CAPABILITY_SET = frozenset({
    "native_carbon",
    "trend",
    "comparison",
    "anomaly_detection",
    "what_if",
    "raw_data",
    "asset_discovery",
})


class StubAdapter(ManufacturingAdapter):
    """Deterministic adapter for integration/pipeline tests.

    Returns fixed values so tests don't depend on external services.
    """

    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        value, unit = _METRIC_VALUES.get(metric.value, (0.0, ""))
        return KPIResult(
            metric=metric,
            value=value,
            unit=unit,
            asset_id=asset_id,
            period=period,
            timestamp=datetime.now(tz=timezone.utc),
        )

    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        value, unit = _METRIC_VALUES.get(metric.value, (0.0, ""))
        items = [
            ComparisonItem(
                asset_id=aid,
                value=value + i * 2.0,
                rank=i + 1,
            )
            for i, aid in enumerate(asset_ids)
        ]
        return ComparisonResult(
            metric=metric,
            items=items,
            winner_id=asset_ids[0],
            difference=2.0 * (len(asset_ids) - 1) if len(asset_ids) > 1 else 0.0,
            unit=unit,
            period=period,
        )

    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        value, unit = _METRIC_VALUES.get(metric.value, (0.0, ""))
        now = datetime.now(tz=timezone.utc)
        points = [
            DataPoint(
                timestamp=now,
                value=value + i * 0.5,
            )
            for i in range(7)
        ]
        return TrendResult(
            metric=metric,
            asset_id=asset_id,
            data_points=points,
            direction="stable",
            change_percent=0.0,
            period=period,
            granularity=granularity,
        )

    async def get_raw_data(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> list[DataPoint]:
        value, _unit = _METRIC_VALUES.get(metric.value, (0.0, ""))
        now = datetime.now(tz=timezone.utc)
        return [
            DataPoint(timestamp=now, value=value + offset)
            for offset in (0.0, 1.0, -0.5)
        ]

    async def list_assets(self) -> list[Asset]:
        return [
            Asset(
                asset_id=name,
                display_name=name,
                asset_type="line" if name.startswith("Line") else "machine",
                aliases=[name.lower(), name.replace("-", " ").lower()],
            )
            for name in _DEMO_ASSETS
        ]

    def supports_capability(self, capability: str) -> bool:
        return capability in _CAPABILITY_SET

    def supports_asset_discovery(self) -> bool:
        return True

    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> AnomalyResult:
        return AnomalyResult(
            is_anomalous=False,
            anomalies=[],
            severity="none",
            asset_id=asset_id,
            metric=metric,
        )

    async def what_if(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        parameter: str,
        change_percent: float,
        period: TimePeriod,
    ) -> WhatIfResult:
        value, unit = _METRIC_VALUES.get(metric.value, (0.0, ""))
        projected = value * (1 + change_percent / 100)
        return WhatIfResult(
            scenario_name=parameter,
            target_metric=metric,
            baseline=value,
            projected=projected,
            delta=projected - value,
            delta_percent=change_percent,
            confidence=0.85,
            factors={parameter: change_percent},
            unit=unit,
        )
