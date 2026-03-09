"""Intent-to-handler and intent-to-metric mapping tables."""

from __future__ import annotations

from skill.domain.models import CanonicalMetric

INTENT_METRIC_MAP: dict[str, CanonicalMetric] = {
    "kpi.energy.per_unit": CanonicalMetric.ENERGY_PER_UNIT,
    "kpi.energy.total": CanonicalMetric.ENERGY_TOTAL,
    "kpi.oee": CanonicalMetric.OEE,
    "kpi.scrap_rate": CanonicalMetric.SCRAP_RATE,
    "kpi.peak_demand": CanonicalMetric.PEAK_DEMAND,
    "kpi.peak_tariff_exposure": CanonicalMetric.PEAK_TARIFF_EXPOSURE,
    "kpi.rework_rate": CanonicalMetric.REWORK_RATE,
    "kpi.material_efficiency": CanonicalMetric.MATERIAL_EFFICIENCY,
    "kpi.recycled_content": CanonicalMetric.RECYCLED_CONTENT,
    "kpi.supplier_lead_time": CanonicalMetric.SUPPLIER_LEAD_TIME,
    "kpi.supplier_defect_rate": CanonicalMetric.SUPPLIER_DEFECT_RATE,
    "kpi.supplier_on_time": CanonicalMetric.SUPPLIER_ON_TIME,
    "kpi.supplier_co2_per_kg": CanonicalMetric.SUPPLIER_CO2_PER_KG,
    "kpi.throughput": CanonicalMetric.THROUGHPUT,
    "kpi.cycle_time": CanonicalMetric.CYCLE_TIME,
    "kpi.changeover_time": CanonicalMetric.CHANGEOVER_TIME,
    "kpi.co2.per_unit": CanonicalMetric.CO2_PER_UNIT,
    "kpi.co2.total": CanonicalMetric.CO2_TOTAL,
    "kpi.co2.per_batch": CanonicalMetric.CO2_PER_BATCH,
}

NON_KPI_INTENT_MAP: tuple[tuple[str, str], ...] = (
    ("greeting.intent", "handle_greeting"),
    ("help.intent", "handle_help"),
    ("compare.energy.intent", "handle_compare_energy"),
    ("trend.scrap.intent", "handle_trend_scrap"),
    ("trend.energy.intent", "handle_trend_energy"),
    ("anomaly.production.check.intent", "handle_anomaly_check"),
    ("whatif.temperature.intent", "handle_whatif_temperature"),
    ("control.device.turn_on.intent", "handle_control_turn_on"),
    ("control.device.turn_off.intent", "handle_control_turn_off"),
    ("status.system.show.intent", "handle_status_system_show"),
    ("status.profile.show.intent", "handle_status_profile_show"),
    ("list.assets.intent", "handle_list_assets"),
    ("help.capabilities.list.intent", "handle_help_capabilities_list"),
)
