---
applyTo: "**"
---
# DEC Compliance Guide

> **Purpose:** Reference guide for Design Decisions (DEC-001 to DEC-007) with examples and anti-patterns.

---

## What are DECs?

**DEC = Design Decision**

**DEC-001 to DEC-007:** Architecture principles (defined at project start)
**DEC-008+:** Runtime decisions made during development

This file covers **DEC-001 to DEC-007** only.

---

## DEC-001: Platform-Agnostic Design

**Principle:** AVAROS works with ANY backend platform, not just RENERYO.

### ✅ GOOD: Platform-agnostic intent handler

```python
# skill/__init__.py
@intent_handler("kpi.energy.per_unit.intent")
def handle_kpi_energy(self, message):
    # Generic query - no platform mentioned
    result = self.query_dispatcher.get_kpi(
        metric="energy_per_unit",
        timeframe=TimeFrame.THIS_WEEK
    )
    self.speak_dialog("kpi.energy.response", {"value": result.value})
```

### ❌ BAD: Platform-specific code in skill

```python
# skill/__init__.py - DON'T DO THIS
@intent_handler("kpi.energy.per_unit.intent")
def handle_kpi_energy(self, message):
    # ❌ Hardcoded RENERYO adapter
    adapter = RENERYOAdapter()
    seu_value = adapter.get_seu()  # ❌ Platform-specific metric name
    
    # ❌ Hardcoded RENERYO URL
    response = requests.get("https://reneryo.com/api/energy")
```

### Where Platform-Specific Code Belongs

**✅ Allowed:** Inside adapter implementations (`skill/adapters/reneryo.py`)
**❌ Forbidden:** Intent handlers, QueryDispatcher, domain models

---

## DEC-002: Universal Metric Framework

**Principle:** Use canonical metric names, not platform-specific terms.

### Canonical Metrics Reference

| Domain | AVAROS Canonical | RENERYO Term | SAP Term | Siemens Term |
|--------|------------------|--------------|----------|--------------|
| Energy per unit | `energy_per_unit` | `seu` | `energyPerPiece` | `specificEnergy` |
| Scrap rate | `scrap_rate` | `scrap_pct` | `scrapPercentage` | `wasteRatio` |
| OEE | `oee` | `oee_score` | `oeeValue` | `overallEquipmentEfficiency` |

### ✅ GOOD: Using canonical metrics

```python
# skill/use_cases/query_dispatcher.py
def get_kpi(self, metric: str, timeframe: TimeFrame) -> KPIResult:
    """
    metric: Canonical name like 'energy_per_unit', 'scrap_rate'
    """
    # Adapter translates canonical → platform-specific
    return self.adapter.get_kpi(metric, timeframe)

# skill/adapters/reneryo.py
def get_kpi(self, metric: str, timeframe: TimeFrame) -> KPIResult:
    # Map canonical → RENERYO-specific
    reneryo_metric = METRIC_MAP[metric]  # 'energy_per_unit' → 'seu'
    response = self._api_client.get(f"/metrics/{reneryo_metric}")
    
    # Return canonical format
    return KPIResult(
        metric=metric,  # ✅ Canonical name
        value=response["value"],
        unit="kWh/unit"
    )
```

### ❌ BAD: Platform-specific metrics leak

```python
# skill/__init__.py - DON'T DO THIS
def handle_kpi_energy(self, message):
    # ❌ Using RENERYO-specific term 'seu'
    result = self.query_dispatcher.get_kpi("seu", TimeFrame.THIS_WEEK)
```

### Adding New Canonical Metrics

If you need a new metric:
1. Check if it exists in Universal Metric Framework
2. If not, propose canonical name (e.g., `water_per_unit`)
3. Update all adapters to map their platform term → canonical
4. Document in `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`

---

## DEC-003: Clean Architecture

**Principle:** Domain never imports from infrastructure layers.

### Layer Dependency Rules

```
┌─────────────────────────────────────┐
│  Presentation (skill/, web/)        │  ← Can import from Domain & Use Cases
├─────────────────────────────────────┤
│  Use Cases (use_cases/)             │  ← Can import from Domain only
├─────────────────────────────────────┤
│  Domain (domain/)                   │  ← Imports NOTHING from other layers
├─────────────────────────────────────┤
│  Infrastructure (adapters/)         │  ← Can import Domain for interfaces
└─────────────────────────────────────┘
```

### ✅ GOOD: Proper layer separation

```python
# skill/domain/models.py (Domain layer)
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class KPIResult:
    metric: str
    value: float
    unit: str
    timestamp: datetime
    # ✅ No imports from adapters or use_cases
```

```python
# skill/use_cases/query_dispatcher.py (Use Case layer)
from skill.domain.models import KPIResult  # ✅ Import from domain OK
from skill.adapters.base import ManufacturingAdapter  # ✅ Import adapter interface OK

class QueryDispatcher:
    def __init__(self, adapter: ManufacturingAdapter):
        self.adapter = adapter
```

```python
# skill/__init__.py (Presentation layer)
from skill.use_cases.query_dispatcher import QueryDispatcher  # ✅ Import use cases OK
from skill.domain.models import KPIResult  # ✅ Import domain OK
```

### ❌ BAD: Violating layer boundaries

```python
# skill/domain/models.py - DON'T DO THIS
from skill.adapters.reneryo import RENERYOAdapter  # ❌ Domain importing infrastructure!

@dataclass
class KPIResult:
    def fetch_from_reneryo(self):  # ❌ Domain shouldn't know about adapters
        adapter = RENERYOAdapter()
        return adapter.get_kpi()
```

### Dependency Inversion

If domain needs behavior, use abstractions (ABCs):

```python
# skill/adapters/base.py (Interface in infrastructure)
from abc import ABC, abstractmethod
from skill.domain.models import KPIResult  # ✅ Adapter can import domain

class ManufacturingAdapter(ABC):
    @abstractmethod
    def get_kpi(self, metric: str) -> KPIResult:
        """Adapter interface - domain doesn't import this."""
        pass
```

---

## DEC-004: Immutable Domain Models

**Principle:** Domain models are frozen dataclasses (immutable after creation).

### ✅ GOOD: Immutable models

```python
from dataclasses import dataclass

@dataclass(frozen=True)  # ✅ Immutable
class KPIResult:
    metric: str
    value: float
    unit: str
    timestamp: datetime
    metadata: dict = None
    
    def __post_init__(self):
        # ✅ Can validate in __post_init__, but can't mutate after creation
        if self.value < 0:
            raise ValueError("KPI value cannot be negative")
```

Usage:
```python
result = KPIResult(metric="energy_per_unit", value=45.2, unit="kWh/unit", timestamp=now())
# result.value = 50  # ❌ Raises FrozenInstanceError - good!
```

### ❌ BAD: Mutable models

```python
@dataclass  # ❌ Not frozen - allows mutation
class KPIResult:
    metric: str
    value: float
    
    def update_value(self, new_value):  # ❌ Mutating method - bad design
        self.value = new_value
```

### Why Immutability Matters

1. **Thread safety** - Can share instances across async tasks
2. **Predictability** - Value can't change unexpectedly
3. **Hashable** - Can use in sets/dicts (add `unsafe_hash=True` if needed)
4. **Easier testing** - No hidden state changes

### Making Immutable Models Hashable

If you need to use model in a set:

```python
@dataclass(frozen=True, unsafe_hash=True)  # ✅ Now hashable
class KPIResult:
    metric: str
    value: float
    
# Now you can:
results = {result1, result2, result3}  # ✅ Works
```

---

## DEC-005: Zero-Config First Run

**Principle:** `docker compose up` → working system. No config editing required.

### ✅ GOOD: Works out-of-box

```python
# skill/adapters/factory.py
def create_adapter() -> ManufacturingAdapter:
    """Create adapter based on settings, fall back to MockAdapter."""
    platform = os.environ.get("AVAROS_PLATFORM")
    
    if not platform:
        # ✅ No config → use mock data for demo
        logger.info("No platform configured, using MockAdapter")
        return MockAdapter()
    
    if platform == "reneryo":
        return RENERYOAdapter()
    elif platform == "sap":
        return SAPAdapter()
    else:
        raise ValueError(f"Unknown platform: {platform}")
```

```yaml
# docker-compose.yml
services:
  avaros:
    image: avaros:latest
    environment:
      # ✅ Optional config - works without it
      AVAROS_PLATFORM: ${AVAROS_PLATFORM:-}  # Empty by default
```

### ❌ BAD: Requires configuration to start

```python
# skill/adapters/factory.py - DON'T DO THIS
def create_adapter() -> ManufacturingAdapter:
    platform = os.environ["AVAROS_PLATFORM"]  # ❌ Crashes if not set
    
    if platform == "reneryo":
        return RENERYOAdapter()
    else:
        raise ValueError("Platform required!")  # ❌ No fallback
```

### First-Run Experience

User journey:
1. `git clone` → `docker compose up` → ✅ **Works immediately with mock data**
2. User explores system, sees demo KPIs
3. User decides to connect to RENERYO
4. User configures via Web UI (not editing files!)
5. System switches to RENERYO adapter

**Key principle:** Configuration is optional enhancement, not requirement.

---

## DEC-006: Settings Service Pattern

**Principle:** All configuration through SettingsService. No hardcoded credentials.

### ✅ GOOD: Using SettingsService

```python
# skill/adapters/reneryo.py
from skill.services.settings import SettingsService

class RENERYOAdapter:
    def __init__(self, settings: SettingsService):
        self.settings = settings
    
    def get_kpi(self, metric: str) -> KPIResult:
        # ✅ Get credentials from SettingsService
        config = self.settings.get_platform_config("reneryo")
        api_key = config["api_key"]
        base_url = config["base_url"]
        
        response = requests.get(
            f"{base_url}/metrics/{metric}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        return self._map_response(response)
```

### ❌ BAD: Hardcoded credentials

```python
# skill/adapters/reneryo.py - DON'T DO THIS
class RENERYOAdapter:
    def get_kpi(self, metric: str):
        # ❌ Hardcoded URL
        base_url = "https://reneryo.com/api"
        
        # ❌ Hardcoded API key
        api_key = "sk_live_abc123xyz"
        
        # ❌ Reading env var directly (bypasses SettingsService)
        api_key = os.environ["RENERYO_API_KEY"]
```

### Where Settings Come From

```
User Input (Web UI) → SettingsService → Encrypted Storage → Adapter
```

SettingsService handles:
- Encryption at rest
- Access control (RBAC)
- Audit logging
- Defaults and validation

---

## DEC-007: Intelligence in Orchestration

**Principle:** Adapters are dumb data fetchers. Intelligence lives in QueryDispatcher, DocuBoT, PREVENTION.

### ✅ GOOD: Intelligence in orchestration layer

```python
# skill/use_cases/query_dispatcher.py (Orchestration)
async def get_kpi_with_context(self, metric: str) -> str:
    # 1. Fetch raw data (adapter is dumb)
    kpi_result = self.adapter.get_kpi(metric)
    
    # 2. Check for anomalies (intelligence in PREVENTION service)
    anomaly = await self.prevention_service.check_anomaly(kpi_result)
    
    # 3. Get context from docs (intelligence in DocuBoT)
    context = await self.docubot.find_context(metric)
    
    # 4. Build intelligent response
    if anomaly:
        return f"{kpi_result.value} {kpi_result.unit} (⚠️ {anomaly.severity} anomaly detected). {context}"
    else:
        return f"{kpi_result.value} {kpi_result.unit}. {context}"
```

```python
# skill/adapters/reneryo.py (Adapter - dumb data fetcher)
def get_kpi(self, metric: str) -> KPIResult:
    # ✅ Just fetch and map data - no intelligence
    response = self._api_client.get(f"/metrics/{metric}")
    return KPIResult(
        metric=metric,
        value=response["value"],
        unit=response["unit"],
        timestamp=parse_datetime(response["timestamp"])
    )
```

### ❌ BAD: Intelligence in adapter

```python
# skill/adapters/reneryo.py - DON'T DO THIS
def get_kpi(self, metric: str) -> KPIResult:
    response = self._api_client.get(f"/metrics/{metric}")
    value = response["value"]
    
    # ❌ Anomaly detection in adapter - wrong layer!
    if value > 100:
        anomaly_detected = True
    
    # ❌ Document lookup in adapter - wrong layer!
    docs = self._fetch_related_docs(metric)
    
    # ❌ Complex business logic in adapter - wrong layer!
    if anomaly_detected and docs:
        recommendation = self._generate_recommendation(value, docs)
    
    return KPIResult(...)  # Now coupled to anomaly detection and docs
```

### Why This Matters

**With intelligence in adapters:**
- Adding SAP adapter → must reimplement anomaly detection
- Changing anomaly algorithm → must update EVERY adapter
- Testing anomaly logic → must mock platform APIs

**With intelligence in orchestration:**
- Adding SAP adapter → just map data, intelligence already exists
- Changing anomaly algorithm → update PREVENTION service once
- Testing anomaly logic → test QueryDispatcher with MockAdapter

### Adapter Interface (What Adapters Should Do)

```python
# skill/adapters/base.py
class ManufacturingAdapter(ABC):
    """Adapters are DUMB data fetchers. No business logic."""
    
    @abstractmethod
    def get_kpi(self, metric: str, timeframe: TimeFrame) -> KPIResult:
        """Fetch KPI value. Just data retrieval, no interpretation."""
        pass
    
    @abstractmethod
    def get_raw_data(self, query: DataQuery) -> RawDataResult:
        """Fetch raw time-series data. For intelligence layer to analyze."""
        pass
    
    @abstractmethod
    def compare(self, entities: list[str], metric: str) -> ComparisonResult:
        """Fetch comparison data. Platform does comparison if available."""
        pass
```

**Notice what's NOT in the interface:**
- ❌ `check_anomaly()` - intelligence, not data fetching
- ❌ `get_recommendation()` - intelligence, not data fetching
- ❌ `simulate_whatif()` - intelligence, not data fetching

These belong in QueryDispatcher/DocuBoT/PREVENTION services.

---

## Quick Compliance Checklist

Before committing code, check:

- [ ] **DEC-001:** No platform names in intent handlers, domain, or use cases
- [ ] **DEC-002:** Using canonical metric names (not `seu`, `scrap_pct`, etc.)
- [ ] **DEC-003:** Domain models don't import from adapters/use_cases
- [ ] **DEC-004:** All domain models have `frozen=True`
- [ ] **DEC-005:** Code works without config files (MockAdapter as fallback)
- [ ] **DEC-006:** No hardcoded credentials, all settings via SettingsService
- [ ] **DEC-007:** Adapters only fetch data, intelligence in QueryDispatcher

---

## How Agents Use This File

**@quality agent:**
- Reviews ALL code changes against this checklist
- Flags violations as 🔴 CRITICAL (must fix before merge)

**@pr-review agent:**
- Checks Emre's PRs for DEC violations
- Teaches Emre WHY each principle matters

**@lead-dev agent:**
- References this when implementing features
- Ensures all new code is DEC-compliant

**@planner agent:**
- Breaks down tasks respecting layer boundaries
- Assigns adapter work to Lead, orchestration to Lead, UI to Emre
