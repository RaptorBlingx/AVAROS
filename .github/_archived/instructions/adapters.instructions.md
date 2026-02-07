---
applyTo: "**/adapters/**/*.py"
---
# Manufacturing Adapter Development Rules

## 🎯 Core Principle
> **Adapters are translators, NOT business logic holders**  
> They convert platform-specific API responses into Canonical Manufacturing Data

## Adapter Contract

All adapters MUST implement the `ManufacturingAdapter` ABC with the **5 Query Type Methods**:

```python
class ManufacturingAdapter(ABC):
    def get_kpi(self, metric: CanonicalMetric, asset_id: str, period: TimePeriod) -> KPIResult:
        """QueryType: KPI Retrieval"""
        
    def compare(self, metric: CanonicalMetric, asset_ids: list[str], period: TimePeriod) -> ComparisonResult:
        """QueryType: Comparison"""
        
    def get_trend(self, metric: CanonicalMetric, asset_id: str, period: TimePeriod, granularity: str) -> TrendResult:
        """QueryType: Trend"""
        
    def check_anomaly(self, metric: CanonicalMetric, asset_id: str, threshold: float = None) -> AnomalyResult:
        """QueryType: Anomaly"""
        
    def simulate_whatif(self, scenario: WhatIfScenario) -> WhatIfResult:
        """QueryType: What-If"""
```

## Canonical Metrics (adapters MUST map platform fields to these)

| Domain | Metrics |
|--------|---------|
| Energy | `energy_per_unit`, `energy_total`, `peak_demand` |
| Material | `scrap_rate`, `rework_rate`, `material_efficiency` |
| Supplier | `supplier_lead_time`, `supplier_defect_rate`, `supplier_on_time` |
| Production | `oee`, `throughput`, `cycle_time` |
| Carbon | `co2_per_unit`, `co2_total`, `co2_per_batch` |

## Rules
1. Return canonical types ONLY - never raw API responses or platform DTOs
2. Handle API errors gracefully - raise `AdapterError(user_message, technical_details)`
3. Implement `supports_capability(capability: str) -> bool` for optional features
4. Log all API calls for audit trail with timestamps
5. Use async methods with `aiohttp`
6. Map platform-specific metric names → `CanonicalMetric` enum

## Configuration
- Config loaded from SettingsService (database-backed), NOT YAML files
- Platform credentials entered via Web UI, stored encrypted
- Hot-reload on config change (no container restart)
- Support environment variable overrides for CI/CD only

## Testing
- Every adapter needs a corresponding mock in `tests/mocks/`
- Contract tests verify all 5 query methods return valid canonical types
