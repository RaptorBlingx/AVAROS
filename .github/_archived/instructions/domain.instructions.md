---
applyTo: "**/domain/**/*.py"
---
# Canonical Manufacturing Data Model

## 🎯 Purpose
Canonical models define **manufacturing concepts** that AVAROS understands.  
Platform adapters convert their responses INTO these types.  
Intent handlers ONLY work with canonical types.

## Implementation Rules
- Use Python \`dataclasses\` with \`@dataclass(frozen=True)\` for immutability
- Include type hints for all fields
- Add \`from_dict()\` class method for deserialization
- Use \`Optional[]\` for nullable fields

## Canonical Metric Enum

\`\`\`python
class CanonicalMetric(Enum):
    ENERGY_PER_UNIT = "energy_per_unit"
    ENERGY_TOTAL = "energy_total"
    PEAK_DEMAND = "peak_demand"
    SCRAP_RATE = "scrap_rate"
    REWORK_RATE = "rework_rate"
    MATERIAL_EFFICIENCY = "material_efficiency"
    SUPPLIER_LEAD_TIME = "supplier_lead_time"
    SUPPLIER_DEFECT_RATE = "supplier_defect_rate"
    SUPPLIER_ON_TIME = "supplier_on_time"
    OEE = "oee"
    THROUGHPUT = "throughput"
    CYCLE_TIME = "cycle_time"
    CO2_PER_UNIT = "co2_per_unit"
    CO2_TOTAL = "co2_total"
\`\`\`

## Query Result Types (one per Query Type)

| Query Type | Result Class | Key Fields |
|------------|--------------|------------|
| KPI | \`KPIResult\` | metric, value, unit, asset_id, period |
| Comparison | \`ComparisonResult\` | metric, items[], winner_id |
| Trend | \`TrendResult\` | data_points[], direction, change_percent |
| Anomaly | \`AnomalyResult\` | is_anomalous, anomalies[], severity |
| What-If | \`WhatIfResult\` | baseline, projected, delta, confidence |

## Rules
1. NO platform-specific fields in canonical models
2. Adapters transform API responses INTO canonical types
3. Intent handlers ONLY work with canonical types
4. All models are immutable (frozen=True)
