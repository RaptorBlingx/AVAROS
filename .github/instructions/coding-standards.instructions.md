---
applyTo: "skill/**/*.py,tests/**/*.py"
---
# AVAROS Coding Standards — Quick Reference

> This is a checklist, not a tutorial. Full details in `DEVELOPMENT.md`.

## DEC Compliance Checklist (→ DEVELOPMENT.md L18–L251)

- [ ] DEC-001: No platform names in handlers, domain, or use_cases
- [ ] DEC-002: Canonical metric names only (`energy_per_unit`, not `seu`)
- [ ] DEC-003: Domain never imports from infrastructure layers
- [ ] DEC-004: All domain models use `frozen=True`
- [ ] DEC-005: Works without config (MockAdapter fallback)
- [ ] DEC-006: Credentials via SettingsService, never hardcoded or from env vars directly
- [ ] DEC-007: Adapters only fetch data; intelligence in QueryDispatcher/services

## Code Quality (→ DEVELOPMENT.md L255–L777)

- Type hints on ALL parameters and return values — no exceptions
- Max 20 lines per function — extract helpers if longer
- Max 300 lines per file — split into modules if longer
- Docstrings with Args, Returns, Raises for all public functions
- No bare `except:` — catch specific exceptions only
- Custom exceptions inherit from `AVAROSError`
- Log with context (metric name, adapter, etc.), then re-raise
- Single Responsibility: one reason to change per function/class

## Testing (→ DEVELOPMENT.md L779–L983)

- AAA pattern: Arrange → Act → Assert
- Import REAL production classes — never redefine models locally in test files
- Naming: `test_{function}_{scenario}_{expected}`
- Coverage targets: Domain 100%, Adapters 90%+, Use Cases 95%+, Handlers 80%+

## Canonical Metric Names (→ DEVELOPMENT.md L1088–L1119)

| Category | Metrics |
|----------|---------|
| **Energy** | `energy_per_unit`, `energy_total`, `peak_demand`, `peak_tariff_exposure` |
| **Material** | `scrap_rate`, `rework_rate`, `material_efficiency`, `recycled_content` |
| **Production** | `oee`, `throughput`, `cycle_time`, `changeover_time` |
| **Carbon** | `co2_per_unit`, `co2_total`, `co2_per_batch` |
| **Supplier** | `supplier_lead_time`, `supplier_defect_rate`, `supplier_on_time`, `supplier_co2_per_kg` |

## Intent Naming (→ DEVELOPMENT.md L1121–L1160)

Format: `{query_type}.{domain}.{detail}.intent`
Examples: `kpi.energy.per_unit`, `compare.supplier.performance`, `trend.scrap.monthly`

## Import Order

```python
# 1. Standard library
import json
from datetime import datetime

# 2. Third-party
from ovos_workshop.decorators import intent_handler

# 3. Local
from skill.domain.models import CanonicalMetric
from skill.adapters.base import ManufacturingAdapter
```
