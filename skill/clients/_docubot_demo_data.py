"""
Demo data for MockDocuBotClient.

Realistic manufacturing document passages and explanation templates
for zero-config deployment (DEC-005). Separated from client logic
to keep files under 300 lines.
"""

from __future__ import annotations


DEMO_PASSAGES: dict[str, list[dict]] = {
    "energy": [
        {
            "text": (
                "Section 4.2 — Energy Optimization: Reducing ambient temperature "
                "by 5°C in the compressor room can decrease energy consumption by "
                "8-12% per unit. Regular maintenance of heat exchangers is critical "
                "for sustaining these gains."
            ),
            "source": "Energy_Management_Manual_v3.pdf",
            "page": 47,
            "relevance": 0.92,
        },
        {
            "text": (
                "Peak demand management: Staggering startup sequences across "
                "production lines reduces peak electrical demand by up to 15%. "
                "See Table 4.3 for recommended startup intervals."
            ),
            "source": "Energy_Management_Manual_v3.pdf",
            "page": 51,
            "relevance": 0.85,
        },
        {
            "text": (
                "Variable frequency drives (VFDs) on compressor motors typically "
                "yield 20-30% energy savings during partial load conditions. "
                "ROI is typically achieved within 18 months."
            ),
            "source": "Equipment_Efficiency_Guide.pdf",
            "page": 23,
            "relevance": 0.78,
        },
    ],
    "material": [
        {
            "text": (
                "Section 3.1 — Scrap Reduction: Statistical process control (SPC) "
                "applied to injection molding reduces scrap rates from 3.5% to "
                "below 1.5%. Key parameters: melt temperature ±2°C, "
                "injection pressure ±5 bar."
            ),
            "source": "Quality_Control_Handbook.pdf",
            "page": 31,
            "relevance": 0.91,
        },
        {
            "text": (
                "Material efficiency improvements: Nesting optimization software "
                "for CNC cutting operations increases material utilization from "
                "85% to 94%. Annual material cost savings: €45,000-€65,000."
            ),
            "source": "Manufacturing_Best_Practices.pdf",
            "page": 89,
            "relevance": 0.87,
        },
    ],
    "carbon": [
        {
            "text": (
                "Section 6.1 — Carbon Footprint Assessment: Scope 1 emissions "
                "from on-site natural gas combustion account for 40% of total "
                "CO₂-eq per unit. Transitioning to biogas reduces this by 60%."
            ),
            "source": "Sustainability_Report_2025.pdf",
            "page": 12,
            "relevance": 0.93,
        },
        {
            "text": (
                "Transportation optimization: Consolidating supplier shipments "
                "reduces Scope 3 logistics emissions by 25%. Minimum order "
                "quantities should be aligned with full truck loads."
            ),
            "source": "Supply_Chain_Sustainability.pdf",
            "page": 34,
            "relevance": 0.79,
        },
    ],
    "production": [
        {
            "text": (
                "Section 2.4 — OEE Improvement: The three OEE components "
                "(Availability, Performance, Quality) should be targeted "
                "independently. Typical quick wins: reducing changeover time "
                "with SMED methodology yields 5-8% OEE improvement."
            ),
            "source": "Lean_Manufacturing_Guide.pdf",
            "page": 28,
            "relevance": 0.90,
        },
        {
            "text": (
                "Cycle time reduction: Implementing parallel processing for "
                "quality inspection during machine loading reduces effective "
                "cycle time by 12-18% without capital investment."
            ),
            "source": "Lean_Manufacturing_Guide.pdf",
            "page": 35,
            "relevance": 0.82,
        },
    ],
    "supplier": [
        {
            "text": (
                "Section 5.2 — Supplier Performance: Lead time variability "
                "is the primary driver of safety stock costs. Implementing "
                "vendor-managed inventory (VMI) reduces average lead time "
                "by 30% and variability by 50%."
            ),
            "source": "Supply_Chain_Optimization.pdf",
            "page": 67,
            "relevance": 0.88,
        },
        {
            "text": (
                "Supplier quality management: Incoming inspection sampling "
                "plans based on AQL 1.0 reduce supplier defect pass-through "
                "from 2.1% to 0.3%. Requires supplier quality agreements."
            ),
            "source": "Quality_Control_Handbook.pdf",
            "page": 45,
            "relevance": 0.84,
        },
    ],
}

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

EXPLANATION_TEMPLATES: dict[str, str] = {
    "energy": (
        "Based on the Energy Management Manual (Section 4.2): {context} — "
        "historical data shows energy consumption correlates strongly with "
        "ambient temperature and equipment maintenance schedules. "
        "A 5°C temperature reduction typically yields 8-12% savings per unit."
    ),
    "material": (
        "According to the Quality Control Handbook (Section 3.1): {context} — "
        "scrap rates are primarily driven by process parameter variability. "
        "Statistical process control on key parameters can reduce scrap by 50%."
    ),
    "carbon": (
        "Per the Sustainability Report (Section 6.1): {context} — "
        "Scope 1 emissions from combustion are the largest contributor. "
        "Fuel switching and efficiency improvements have the highest impact."
    ),
    "production": (
        "From the Lean Manufacturing Guide (Section 2.4): {context} — "
        "OEE improvements are best achieved by targeting the weakest "
        "component (Availability, Performance, or Quality) independently."
    ),
    "supplier": (
        "Based on Supply Chain Optimization (Section 5.2): {context} — "
        "lead time variability is the primary cost driver. VMI and "
        "supplier quality agreements provide the most reliable improvements."
    ),
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "energy": [
        "energy", "power", "electricity", "kwh", "demand",
        "tariff", "consumption",
    ],
    "material": [
        "scrap", "waste", "material", "rework", "recycl",
        "efficiency",
    ],
    "carbon": [
        "carbon", "co2", "emission", "footprint", "sustainab",
        "scope",
    ],
    "supplier": [
        "supplier", "lead time", "defect", "delivery", "supply",
        "vendor",
    ],
    "production": [
        "oee", "throughput", "cycle", "changeover", "production",
        "lean",
    ],
}
