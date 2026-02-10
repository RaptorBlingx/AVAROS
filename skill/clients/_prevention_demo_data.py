"""
Demo data for MockPreventionClient.

Realistic anomaly detection and drift monitoring demo responses
for zero-config deployment (DEC-005). Separated from client logic
to keep files under 300 lines.

Categories mirror the canonical metric groups: energy, material,
carbon, production, supplier.
"""

from __future__ import annotations


# =========================================================================
# Anomaly Detection Demo Responses
# =========================================================================

ANOMALY_DESCRIPTIONS: dict[str, dict] = {
    "energy": {
        "anomalous": (
            "Energy consumption per unit spiked {deviation}σ above the "
            "7-day rolling average. This level of deviation typically "
            "indicates equipment degradation or unexpected load changes."
        ),
        "normal": (
            "Energy consumption per unit is within normal operating "
            "range (±1.5σ of the 7-day rolling average). No corrective "
            "action required."
        ),
        "action": (
            "Inspect compressor maintenance schedule and heat exchanger "
            "efficiency. Check for ambient temperature spikes in the "
            "production area."
        ),
    },
    "material": {
        "anomalous": (
            "Material waste rate increased {deviation}σ above baseline. "
            "Pattern suggests process parameter drift in upstream "
            "operations."
        ),
        "normal": (
            "Material waste metrics are within expected bounds. "
            "Current scrap and rework rates align with historical norms."
        ),
        "action": (
            "Review SPC charts for injection parameters (melt temperature, "
            "injection pressure). Verify raw material batch quality."
        ),
    },
    "carbon": {
        "anomalous": (
            "Carbon emissions per unit rose {deviation}σ above the "
            "monthly baseline. Likely correlated with increased energy "
            "consumption or fuel mix changes."
        ),
        "normal": (
            "Carbon emissions are tracking within expected ranges. "
            "No significant deviation from the sustainability targets."
        ),
        "action": (
            "Check fuel source composition and energy consumption "
            "patterns. Verify Scope 1 emission factors are current."
        ),
    },
    "production": {
        "anomalous": (
            "Production efficiency deviated {deviation}σ from the "
            "expected level. OEE components show abnormal variation "
            "in availability."
        ),
        "normal": (
            "Production metrics are operating within normal parameters. "
            "OEE, throughput, and cycle times are stable."
        ),
        "action": (
            "Analyze OEE breakdown (Availability, Performance, Quality) "
            "to identify the root cause. Check for unplanned downtime."
        ),
    },
    "supplier": {
        "anomalous": (
            "Supplier performance metric shifted {deviation}σ from "
            "the quarterly average. Lead time variability shows "
            "abnormal increase."
        ),
        "normal": (
            "Supplier metrics are within acceptable ranges. "
            "Lead times and quality rates are stable."
        ),
        "action": (
            "Contact supplier quality team for root cause. "
            "Review recent delivery and inspection records."
        ),
    },
}


# =========================================================================
# Drift Monitoring Demo Responses
# =========================================================================

DRIFT_PROFILES: dict[str, dict] = {
    "energy": {
        "has_drift": True,
        "direction": "improving",
        "rate": -0.3,
        "description": (
            "Energy per unit shows a downward trend of -0.3 kWh/unit "
            "per day over the analyzed period. This improvement aligns "
            "with recent maintenance activities and optimization efforts."
        ),
    },
    "material": {
        "has_drift": False,
        "direction": "stable",
        "rate": 0.0,
        "description": (
            "Material waste metrics show no significant drift. "
            "Scrap and rework rates remain within ±0.1% of the "
            "30-day average."
        ),
    },
    "carbon": {
        "has_drift": True,
        "direction": "improving",
        "rate": -0.15,
        "description": (
            "Carbon emissions per unit are trending downward at "
            "-0.15 kg CO₂-eq/unit per day. This tracks with the "
            "reported energy efficiency improvements."
        ),
    },
    "production": {
        "has_drift": True,
        "direction": "improving",
        "rate": 0.5,
        "description": (
            "OEE shows a positive trend of +0.5 percentage points "
            "per day. Recent changeover time reductions are the "
            "primary driver."
        ),
    },
    "supplier": {
        "has_drift": True,
        "direction": "degrading",
        "rate": 0.4,
        "description": (
            "Supplier lead time shows an upward trend of +0.4 days "
            "per period. Consider engaging the supplier quality team "
            "to investigate root causes."
        ),
    },
}


# =========================================================================
# Metric-to-Category Mapping (shared with DocuBoT)
# =========================================================================

METRIC_CATEGORY_MAP: dict[str, str] = {
    "energy_per_unit": "energy",
    "energy_total": "energy",
    "peak_demand": "energy",
    "peak_tariff_exposure": "energy",
    "scrap_rate": "material",
    "rework_rate": "material",
    "material_efficiency": "material",
    "recycled_content": "material",
    "supplier_lead_time": "supplier",
    "supplier_defect_rate": "supplier",
    "supplier_on_time": "supplier",
    "supplier_co2_per_kg": "supplier",
    "oee": "production",
    "throughput": "production",
    "cycle_time": "production",
    "changeover_time": "production",
    "co2_per_unit": "carbon",
    "co2_total": "carbon",
    "co2_per_batch": "carbon",
}

# Metrics that the mock treats as anomalous for demo purposes.
# Deterministic: same metric always produces the same result.
ANOMALOUS_METRICS: set[str] = {
    "energy_per_unit",
    "peak_demand",
    "co2_per_unit",
}
