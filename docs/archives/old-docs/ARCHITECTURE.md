# AVAROS Architecture Design

**Document Owner:** AVAROS Architect  
**Status:** 🟡 DRAFT  
**Last Updated:** *(auto-updated by agent)*

---

## 📋 Quick Reference

| Aspect | Decision |
|--------|----------|
| Voice Platform | OVOS (Open Voice OS) |
| Design Pattern | Platform-Agnostic Adapters |
| Deployment | Docker Compose (Zero-Config) |
| Query Types | 5 (get_kpi, compare, get_trend, check_anomaly, simulate_whatif) |

---

## 🎯 Design Status

| Component | Status | Notes |
|-----------|--------|-------|
| System Overview | ✅ DONE | High-level architecture defined |
| Data Flow | ✅ DONE | 5 query types documented |
| Component Diagram | ✅ DONE | Clean Architecture layers |
| Interface Definitions | ✅ DONE | ManufacturingAdapter ABC |
| Folder Structure | ✅ DONE | Scaffolded with boilerplate |

**Legend:** ⬜ TODO | 🔄 IN PROGRESS | ✅ DONE | ⚠️ NEEDS REVISION

---

## 1. System Overview

*(Architect will fill this section)*

### 1.1 Golden Rule
> **AVAROS understands manufacturing concepts; Adapters understand platform APIs**

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Voice Layer (OVOS)                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │              AVAROS Skill                        │   │
│  │  ┌─────────────┐     ┌──────────────────────┐   │   │
│  │  │Intent Files │────▶│ Query Dispatcher     │   │   │
│  │  │(5 types)    │     │ (routes by type)     │   │   │
│  │  └─────────────┘     └──────────┬───────────┘   │   │
│  └──────────────────────────────────│──────────────┘   │
└─────────────────────────────────────│──────────────────┘
                                      │
┌─────────────────────────────────────▼──────────────────┐
│              Adapter Layer (Platform-Agnostic)          │
│  ┌────────────────────────────────────────────────┐    │
│  │         ManufacturingAdapter (ABC)              │    │
│  │  • get_kpi()      • compare()                   │    │
│  │  • get_trend()    • check_anomaly()             │    │
│  │  • simulate_whatif()                            │    │
│  └────────────────────────────────────────────────┘    │
│       │              │              │                   │
│  ┌────▼────┐   ┌────▼────┐   ┌────▼────┐              │
│  │MockAdapt│   │RENERYO  │   │Future   │              │
│  │(demo)   │   │Adapter  │   │Adapters │              │
│  └─────────┘   └─────────┘   └─────────┘              │
└─────────────────────────────────────────────────────────┘
```

*(Expand with actual design decisions)*

---

## 2. Component Design

### 2.1 OVOS Skill Structure

```
skill/
├── __init__.py           # OVOSSkill class + handlers
├── query_dispatcher.py   # Routes to adapter methods
├── domain/
│   ├── types.py          # CanonicalMetric, KPIResult, etc.
│   └── exceptions.py     # Domain exceptions
├── adapters/
│   ├── base.py           # ManufacturingAdapter ABC
│   ├── factory.py        # AdapterFactory
│   └── mock_adapter.py   # Demo/testing adapter
└── locale/en-us/
    ├── *.intent          # Intent files
    └── *.dialog          # Response templates
```

### 2.2 The 5 Query Types

| Query Type | Intent Pattern | Adapter Method | Return Type |
|------------|---------------|----------------|-------------|
| get_kpi | `kpi.{metric}.{asset}.intent` | `get_kpi()` | KPIResult |
| compare | `compare.{metric}.intent` | `compare()` | ComparisonResult |
| get_trend | `trend.{metric}.intent` | `get_trend()` | TrendResult |
| check_anomaly | `anomaly.{asset}.intent` | `check_anomaly()` | AnomalyResult |
| simulate_whatif | `whatif.{scenario}.intent` | `simulate_whatif()` | WhatIfResult |

### 2.3 Canonical Data Types

```python
class KPIResult:
    metric: CanonicalMetric
    value: float
    unit: str
    timestamp: datetime
    asset_id: str
    period: Period

class TrendResult:
    metric: CanonicalMetric
    data_points: List[DataPoint]
    trend_direction: Literal['up', 'down', 'stable']
    
# ... (Architect expands as needed)
```

---

## 3. Data Flow

*(Architect will document request/response flows)*

### 3.1 Query Flow Example

```
User: "What's the OEE for Line-1?"
         │
         ▼
    ┌─────────────┐
    │ OVOS Core   │  (speech-to-text)
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Intent Match│  → kpi.oee.intent
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────┐
    │ QueryDispatcher     │  route(QueryType.GET_KPI)
    └──────┬──────────────┘
           │
           ▼
    ┌─────────────────────┐
    │ ManufacturingAdapter│  get_kpi(OEE, "Line-1", today)
    └──────┬──────────────┘
           │
           ▼
    ┌─────────────┐
    │ KPIResult   │  → {value: 82.5, unit: "%", ...}
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Dialog      │  "The OEE for Line-1 is 82.5 percent"
    └─────────────┘
```

---

## 4. Interface Definitions

### 4.1 ManufacturingAdapter ABC

The core abstraction that all platform adapters implement:

```python
class ManufacturingAdapter(ABC):
    """Platform-agnostic adapter interface for manufacturing data."""
    
    # Query Type 1: KPI Retrieval
    @abstractmethod
    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult: ...
    
    # Query Type 2: Comparison
    @abstractmethod
    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult: ...
    
    # Query Type 3: Trend Analysis
    @abstractmethod
    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult: ...
    
    # Query Type 4: Anomaly Detection
    @abstractmethod
    async def check_anomaly(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        threshold: float | None = None,
    ) -> AnomalyResult: ...
    
    # Query Type 5: What-If Simulation
    @abstractmethod
    async def simulate_whatif(
        self,
        scenario: WhatIfScenario,
    ) -> WhatIfResult: ...
```

### 4.2 Canonical Metrics

```python
class CanonicalMetric(Enum):
    # Energy
    ENERGY_PER_UNIT = "energy_per_unit"
    ENERGY_TOTAL = "energy_total"
    PEAK_DEMAND = "peak_demand"
    
    # Material
    SCRAP_RATE = "scrap_rate"
    REWORK_RATE = "rework_rate"
    MATERIAL_EFFICIENCY = "material_efficiency"
    
    # Production
    OEE = "oee"
    THROUGHPUT = "throughput"
    CYCLE_TIME = "cycle_time"
    
    # Carbon
    CO2_PER_UNIT = "co2_per_unit"
    CO2_TOTAL = "co2_total"
```

### 4.3 Result Types

| Query Type | Result Class | Key Fields |
|------------|--------------|------------|
| get_kpi | `KPIResult` | metric, value, unit, asset_id, period |
| compare | `ComparisonResult` | items[], winner_id, difference |
| get_trend | `TrendResult` | data_points[], direction, change_percent |
| check_anomaly | `AnomalyResult` | is_anomalous, anomalies[], severity |
| simulate_whatif | `WhatIfResult` | baseline, projected, delta_percent, confidence |

---

## 5. Folder Structure (Implemented)

```
avaros-ovos-skill/
├── skill/
│   ├── __init__.py            # OVOSSkill class with intent handlers
│   ├── domain/
│   │   ├── __init__.py        # Domain exports
│   │   ├── models.py          # CanonicalMetric, TimePeriod, etc.
│   │   ├── results.py         # KPIResult, ComparisonResult, etc.
│   │   └── exceptions.py      # AVAROSError hierarchy
│   ├── use_cases/
│   │   ├── __init__.py
│   │   └── query_dispatcher.py # Routes queries to adapters
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py            # ManufacturingAdapter ABC
│   │   ├── mock.py            # MockAdapter (zero-config)
│   │   └── factory.py         # AdapterFactory
│   └── locale/en-us/
│       ├── *.intent           # Intent files (5 query types)
│       └── *.dialog           # Response templates
├── tests/
│   ├── conftest.py            # Shared fixtures
│   ├── test_domain/           # Domain model tests
│   └── test_adapters/         # Adapter contract tests
├── docker/
│   └── Dockerfile             # Multi-stage build
├── docker-compose.yml         # Zero-config deployment
├── requirements.txt
├── .env.example
└── docs/
    ├── ARCHITECTURE.md        # This document
    ├── DECISIONS.md           # ADR log
    └── TODO.md                # Task tracking
```

---

## 6. Decisions & Rationale

See [docs/DECISIONS.md](DECISIONS.md) for all architectural decisions with rationale.

---

## 7. WASABI Proposal KPI Alignment

| Proposal KPI | Target | Canonical Metric | How We Measure |
|--------------|--------|------------------|----------------|
| Electricity per unit | ≥8% reduction | `energy_per_unit` | Trend analysis over time |
| Material efficiency | ≥5% improvement | `scrap_rate`, `rework_rate` | Compare before/after |
| CO₂-eq emissions | ≥10% reduction | `co2_per_unit`, `co2_total` | Monthly trend reports |

---

## 8. Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-01-30 | AVAROS Architect | Complete architecture design & scaffolding |

---

**⏭️ Next Step:** Hand off to **AVAROS Task Planner** for implementation task breakdown.
