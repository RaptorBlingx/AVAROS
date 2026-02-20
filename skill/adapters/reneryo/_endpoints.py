"""
RENERYO API Endpoint Constants.

Maps canonical metrics to RENERYO REST API paths for both
mock (per-metric routes) and native (shared measurement endpoints) formats.
"""

from __future__ import annotations

from skill.domain.models import CanonicalMetric

# Mock API endpoints (used by reneryo-mock server for per-metric routes)
ENDPOINT_MAP: dict[CanonicalMetric, str] = {
    # Energy Metrics
    CanonicalMetric.ENERGY_PER_UNIT: "/api/v1/kpis/energy/per-unit",
    CanonicalMetric.ENERGY_TOTAL: "/api/v1/kpis/energy/total",
    CanonicalMetric.PEAK_DEMAND: "/api/v1/kpis/energy/peak-demand",
    CanonicalMetric.PEAK_TARIFF_EXPOSURE: "/api/v1/kpis/energy/tariff-exposure",
    # Material Metrics
    CanonicalMetric.SCRAP_RATE: "/api/v1/kpis/material/scrap-rate",
    CanonicalMetric.REWORK_RATE: "/api/v1/kpis/material/rework-rate",
    CanonicalMetric.MATERIAL_EFFICIENCY: "/api/v1/kpis/material/efficiency",
    CanonicalMetric.RECYCLED_CONTENT: "/api/v1/kpis/material/recycled-content",
    # Supplier Metrics
    CanonicalMetric.SUPPLIER_LEAD_TIME: "/api/v1/kpis/supplier/lead-time",
    CanonicalMetric.SUPPLIER_DEFECT_RATE: "/api/v1/kpis/supplier/defect-rate",
    CanonicalMetric.SUPPLIER_ON_TIME: "/api/v1/kpis/supplier/on-time",
    CanonicalMetric.SUPPLIER_CO2_PER_KG: "/api/v1/kpis/supplier/co2-per-kg",
    # Production Metrics
    CanonicalMetric.OEE: "/api/v1/kpis/production/oee",
    CanonicalMetric.THROUGHPUT: "/api/v1/kpis/production/throughput",
    CanonicalMetric.CYCLE_TIME: "/api/v1/kpis/production/cycle-time",
    CanonicalMetric.CHANGEOVER_TIME: "/api/v1/kpis/production/changeover-time",
    # Carbon Metrics
    CanonicalMetric.CO2_PER_UNIT: "/api/v1/kpis/carbon/per-unit",
    CanonicalMetric.CO2_TOTAL: "/api/v1/kpis/carbon/total",
    CanonicalMetric.CO2_PER_BATCH: "/api/v1/kpis/carbon/per-batch",
}

# Real RENERYO API endpoints
REAL_METER_ENDPOINT = "/api/u/measurement/meter/item"
REAL_SEU_ITEMS_ENDPOINT = "/api/u/measurement/seu/item"
REAL_SEU_NAMES_ENDPOINT = "/api/u/measurement/seu/names"
REAL_SEU_GRAPH_ENDPOINT = "/api/u/measurement/seu/graph"
REAL_SEU_VALUES_ENDPOINT = "/api/u/measurement/seu/item/{seu_id}/values"
REAL_METRIC_ENDPOINT = "/api/u/measurement/metric/item"
REAL_METRIC_NAMES_ENDPOINT = "/api/u/measurement/metric/names"
REAL_METRIC_RESOURCES_ENDPOINT = "/api/u/measurement/metric/resources"
REAL_METRIC_RESOURCE_VALUES_ENDPOINT = "/api/u/measurement/metric/resource/{resource_id}/values"

# Metrics available in the real RENERYO API (energy monitoring platform)
REAL_ENERGY_METRICS: frozenset[CanonicalMetric] = frozenset({
    CanonicalMetric.ENERGY_PER_UNIT,
    CanonicalMetric.ENERGY_TOTAL,
    CanonicalMetric.PEAK_DEMAND,
    CanonicalMetric.PEAK_TARIFF_EXPOSURE,
})

REAL_PRODUCTION_METRICS: frozenset[CanonicalMetric] = frozenset({
    CanonicalMetric.OEE,
    CanonicalMetric.SCRAP_RATE,
    CanonicalMetric.THROUGHPUT,
    CanonicalMetric.CYCLE_TIME,
    CanonicalMetric.CHANGEOVER_TIME,
})

REAL_SUPPORTED_METRICS: frozenset[CanonicalMetric] = frozenset(
    set(REAL_ENERGY_METRICS) | set(REAL_PRODUCTION_METRICS),
)

SUPPORTED_CAPABILITIES: set[str] = {"carbon", "realtime"}
