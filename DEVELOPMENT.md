# AVAROS Development Guide

> **Purpose:** Standards, patterns, and best practices for all AVAROS contributors.  
> **Last Updated:** February 6, 2026

---

## Table of Contents

1. [Architecture Principles (DEC-001 to DEC-007)](#architecture-principles)
2. [Code Quality Standards](#code-quality-standards)
3. [Testing Standards](#testing-standards)
4. [Git Workflow](#git-workflow)
5. [Quick Reference](#quick-reference)

---

## Architecture Principles

AVAROS follows **Clean Architecture** with seven core design decisions (DEC-001 to DEC-007). Every code change must comply with these principles.

### DEC-001: Platform-Agnostic Design

**Principle:** AVAROS works with ANY backend platform, not just RENERYO.

✅ **GOOD: Platform-agnostic intent handler**
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

❌ **BAD: Platform-specific code in skill**
```python
# skill/__init__.py - DON'T DO THIS
@intent_handler("kpi.energy.per_unit.intent")
def handle_kpi_energy(self, message):
    adapter = RENERYOAdapter()  # ❌ Hardcoded platform
    seu_value = adapter.get_seu()  # ❌ Platform-specific metric
```

**Where platform-specific code belongs:**
- ✅ **Allowed:** Inside adapter implementations (`skill/adapters/reneryo.py`)
- ❌ **Forbidden:** Intent handlers, QueryDispatcher, domain models

---

### DEC-002: Universal Metric Framework

**Principle:** Use canonical metric names, not platform-specific terms.

**Canonical Metrics Reference:**

| Domain | AVAROS Canonical | RENERYO Term | Example Platform Terms |
|--------|------------------|--------------|------------------------|
| Energy per unit | `energy_per_unit` | `seu` | `energyPerPiece`, `specificEnergy` |
| Scrap rate | `scrap_rate` | `scrap_pct` | `scrapPercentage`, `wasteRatio` |
| OEE | `oee` | `oee_score` | `oeeValue`, `overallEquipmentEfficiency` |

✅ **GOOD: Using canonical metrics**
```python
# Intent handler uses canonical name
result = self.query_dispatcher.get_kpi("energy_per_unit", timeframe)

# Adapter translates to platform-specific
class RENERYOAdapter:
    def get_kpi(self, metric: str, timeframe: TimeFrame) -> KPIResult:
        reneryo_metric = METRIC_MAP[metric]  # 'energy_per_unit' → 'seu'
        response = self._api_client.get(f"/metrics/{reneryo_metric}")
        return KPIResult(metric=metric, value=response["value"], ...)
```

❌ **BAD: Platform-specific metrics leak**
```python
# ❌ Using RENERYO-specific term in skill
result = self.query_dispatcher.get_kpi("seu", timeframe)
```

---

### DEC-003: Clean Architecture

**Principle:** Domain never imports from infrastructure layers.

**Layer Dependency Rules:**
```
┌─────────────────────────────────────┐
│  Presentation (skill/, web/)        │  ← Can import Domain & Use Cases
├─────────────────────────────────────┤
│  Use Cases (use_cases/)             │  ← Can import Domain only
├─────────────────────────────────────┤
│  Domain (domain/)                   │  ← Imports NOTHING from other layers
├─────────────────────────────────────┤
│  Infrastructure (adapters/)         │  ← Can import Domain for interfaces
└─────────────────────────────────────┘
```

✅ **GOOD: Proper layer separation**
```python
# skill/domain/models.py (Domain layer)
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class KPIResult:
    metric: str
    value: float
    # ✅ No imports from adapters or use_cases
```

❌ **BAD: Violating layer boundaries**
```python
# skill/domain/models.py - DON'T DO THIS
from skill.adapters.reneryo import RENERYOAdapter  # ❌ Domain importing infrastructure!
```

---

### DEC-004: Immutable Domain Models

**Principle:** Domain models are frozen dataclasses (immutable after creation).

✅ **GOOD: Immutable models**
```python
from dataclasses import dataclass

@dataclass(frozen=True)  # ✅ Immutable
class KPIResult:
    metric: str
    value: float
    unit: str
    timestamp: datetime
    
# result.value = 50  # ❌ Raises FrozenInstanceError - good!
```

**Why immutability matters:**
- Thread safety - can share instances across async tasks
- Predictability - value can't change unexpectedly
- Hashable - can use in sets/dicts

---

### DEC-005: Zero-Config First Run

**Principle:** `docker compose up` → working system. No config editing required.

✅ **GOOD: Works out-of-box**
```python
def create_adapter() -> ManufacturingAdapter:
    platform = os.environ.get("AVAROS_PLATFORM")
    
    if not platform:
        # ✅ No config → use mock data for demo
        logger.info("No platform configured, using MockAdapter")
        return MockAdapter()
    
    if platform == "reneryo":
        return RENERYOAdapter()
```

**First-run experience:**
1. `git clone` → `docker compose up` → ✅ **Works immediately with mock data**
2. User explores system, sees demo KPIs
3. User configures via Web UI
4. System switches to real adapter

---

### DEC-006: Settings Service Pattern

**Principle:** All configuration through SettingsService. No hardcoded credentials.

✅ **GOOD: Using SettingsService**
```python
class RENERYOAdapter:
    def __init__(self, settings: SettingsService):
        self.settings = settings
    
    def get_kpi(self, metric: str) -> KPIResult:
        # ✅ Get credentials from SettingsService
        config = self.settings.get_platform_config("reneryo")
        api_key = config["api_key"]
        base_url = config["base_url"]
```

❌ **BAD: Hardcoded credentials**
```python
# ❌ Hardcoded URL and API key
base_url = "https://reneryo.com/api"
api_key = "sk_live_abc123xyz"
```

---

### DEC-007: Intelligence in Orchestration

**Principle:** Adapters are dumb data fetchers. Intelligence lives in QueryDispatcher, DocuBoT, PREVENTION.

✅ **GOOD: Intelligence in orchestration layer**
```python
# QueryDispatcher (orchestration)
async def get_kpi_with_context(self, metric: str) -> str:
    # 1. Fetch raw data (adapter is dumb)
    kpi_result = self.adapter.get_kpi(metric)
    
    # 2. Check for anomalies (intelligence in PREVENTION service)
    anomaly = await self.prevention.check_anomaly(kpi_result)
    
    # 3. Get context from docs (intelligence in DocuBoT)
    context = await self.docubot.find_context(metric)
    
    # 4. Build intelligent response
    return self._build_response(kpi_result, anomaly, context)
```

✅ **GOOD: Adapter - dumb data fetcher**
```python
# Adapter - just fetch and map data
def get_kpi(self, metric: str) -> KPIResult:
    response = self._api_client.get(f"/metrics/{metric}")
    return KPIResult(
        metric=metric,
        value=response["value"],
        unit=response["unit"]
    )
```

❌ **BAD: Intelligence in adapter**
```python
# ❌ Adapter doing business logic
def get_kpi(self, metric: str) -> KPIResult:
    value = self._api_client.get(f"/metrics/{metric}")
    
    # ❌ Anomaly detection in adapter - wrong layer!
    if value > 100:
        self._send_alert()
```

**Why this matters:**
- Adding new adapter doesn't require reimplementing anomaly detection
- Changing anomaly algorithm doesn't require updating every adapter
- Testing intelligence doesn't require mocking platform APIs

---

## Code Quality Standards

### Naming Conventions

**Classes:** `PascalCase`
```python
class KPIResult:
class RENERYOAdapter:
class QueryDispatcher:
```

**Functions/Methods:** `snake_case`
```python
def get_kpi(metric: str) -> KPIResult:
def build_response(data: dict) -> str:
def validate_metric_name(name: str) -> bool:
```

**Constants:** `UPPER_SNAKE_CASE`
```python
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
SUPPORTED_METRICS = ["energy_per_unit", "scrap_rate", "oee"]
```

**Abbreviations:**
- ✅ **OK:** `API`, `KPI`, `OEE`, `ID`, `HTTP`, `JSON`
- ❌ **Avoid:** `mgr`, `cfg`, `tmp`, `res`, `req`

---

### Function Standards

#### Max 20 Lines Per Function

Extract helper functions if longer.

❌ **BAD: 50-line function doing too much**
```python
def process_kpi_request(utterance, context, settings):
    # ... 50 lines of parsing, validation, API calls, formatting ...
```

✅ **GOOD: Split into focused functions**
```python
def process_kpi_request(utterance: str, context: dict) -> str:
    metric = extract_metric(utterance)
    timeframe = extract_timeframe(utterance)
    result = fetch_kpi(metric, timeframe)
    return format_response(result)
```

---

#### Single Responsibility

One function = one reason to change.

❌ **BAD: Function does parsing AND validation AND API call**
```python
def get_data(text):
    metric = parse_utterance(text)
    if not is_valid(metric):
        raise ValueError
    return call_api(metric)
```

✅ **GOOD: Separate concerns**
```python
def parse_metric(utterance: str) -> str:
    """Extract metric name from utterance."""
    # parsing logic only

def fetch_kpi(metric: str) -> KPIResult:
    """Fetch KPI from adapter."""
    # API logic only
```

---

#### Type Hints MANDATORY

❌ **BAD: No type hints**
```python
def get_kpi(metric, timeframe):
    return adapter.fetch(metric, timeframe)
```

✅ **GOOD: Complete type hints**
```python
def get_kpi(
    metric: str,
    timeframe: TimeFrame,
    adapter: ManufacturingAdapter
) -> KPIResult:
    """Fetch KPI value for given metric and timeframe.
    
    Args:
        metric: Canonical metric name (e.g., 'energy_per_unit')
        timeframe: Time period for the query
        adapter: Platform adapter implementation
        
    Returns:
        KPIResult with value, unit, and metadata
        
    Raises:
        MetricNotFoundError: If metric is not supported
        AdapterError: If platform API fails
    """
    return adapter.get_kpi(metric, timeframe)
```

---

#### Docstrings Required

All public functions must have docstrings with:
- **Args:** Parameter descriptions
- **Returns:** What the function returns
- **Raises:** What exceptions it can raise
- **Example** (optional): Usage example

---

### File Standards

#### Max 300 Lines Per File

Split into modules if longer.

❌ **BAD: 800-line god file**
```
skill/adapters/reneryo.py  # Everything in one file
```

✅ **GOOD: Modular structure**
```
skill/adapters/reneryo/
    __init__.py
    client.py          # HTTP client (100 lines)
    mapper.py          # Response mapping (120 lines)
    auth.py            # Authentication (80 lines)
```

---

#### Import Order

Always use this order with blank lines between groups:

```python
# Standard library
import json
import logging
from datetime import datetime
from typing import Optional

# Third-party
import aiohttp
from ovos_workshop.decorators import intent_handler

# Local (project imports)
from skill.domain.models import KPIResult
from skill.adapters.base import ManufacturingAdapter
```

---

### Error Handling

#### Never Catch Bare `except:`

❌ **BAD: Catches everything**
```python
try:
    result = adapter.get_kpi(metric)
except:  # ❌ Catches KeyboardInterrupt too!
    return None
```

✅ **GOOD: Specific exception handling**
```python
try:
    result = adapter.get_kpi(metric)
except MetricNotFoundError:
    logger.warning(f"Metric not found: {metric}")
    raise
except AdapterError as e:
    logger.error(f"Adapter failed: {e}", exc_info=True)
    raise
```

---

#### Custom Exceptions Inherit from AvarosError

```python
# skill/domain/exceptions.py
class AvarosError(Exception):
    """Base exception for AVAROS."""
    pass

class MetricNotFoundError(AvarosError):
    """Metric not supported by platform."""
    pass

class AdapterError(AvarosError):
    """Adapter communication failure."""
    pass
```

---

#### Log with Context, Then Re-raise

```python
def get_kpi(metric: str) -> KPIResult:
    try:
        data = adapter.fetch(metric)
        return KPIResult.from_adapter_data(data)
    except AdapterError as e:
        logger.error(
            f"Failed to fetch KPI",
            extra={"metric": metric, "adapter": adapter.name},
            exc_info=True
        )
        raise  # Let caller handle it
```

---

## Testing Standards

### Test Pyramid

```
        /\
       /  \      E2E Tests (10%)
      /────\     - Full voice interaction
     /      \    
    /────────\   Integration Tests (30%)
   /          \  - Adapter + API tests
  /────────────\ - Skill + QueryDispatcher
 /              \
/────────────────\ Unit Tests (60%)
                  - Domain models
                  - Business logic
```

**Golden Rule:** Fast feedback loop. Unit tests run in <2 seconds.

---

### Coverage Requirements

| Code Type | Test Type | Coverage Target |
|-----------|-----------|-----------------|
| **Domain models** | Unit | 100% |
| **Adapter implementations** | Integration (mocked API) | 90%+ |
| **Use cases (QueryDispatcher)** | Unit (mocked adapters) | 95%+ |
| **Intent handlers** | Integration | 80%+ |
| **Web endpoints** | API tests | 90%+ |

---

### Test Naming Convention

**Format:** `test_{function_name}_{scenario}_{expected_result}`

✅ **GOOD names (self-documenting):**
```python
def test_get_kpi_with_valid_metric_returns_kpi_result():
def test_get_kpi_with_unknown_metric_raises_metric_not_found():
def test_get_kpi_with_api_timeout_raises_adapter_error():
def test_build_response_with_none_result_returns_error_dialog():
```

❌ **BAD names (unclear):**
```python
def test_kpi():  # What about KPI?
def test_error():  # What error?
def test_1():  # What does this test?
```

---

### Test Structure: AAA (Arrange-Act-Assert)

```python
def test_get_kpi_with_valid_metric_returns_kpi_result():
    # Arrange: Set up test data and dependencies
    adapter = MockAdapter()
    dispatcher = QueryDispatcher(adapter)
    metric = "energy_per_unit"
    timeframe = TimeFrame.THIS_WEEK
    
    # Act: Execute the function being tested
    result = dispatcher.get_kpi(metric, timeframe)
    
    # Assert: Verify the expected outcome
    assert isinstance(result, KPIResult)
    assert result.metric == "energy_per_unit"
    assert result.value > 0
    assert result.unit == "kWh/unit"
```

**Use comments to separate sections** for readability.

---

### Mocking Pattern

```python
from unittest.mock import Mock, patch

def test_adapter_calls_api_with_correct_params():
    # Mock the HTTP client
    mock_client = Mock()
    mock_client.get.return_value = {"seu": 125.5}
    
    adapter = RENERYOAdapter(client=mock_client)
    result = adapter.get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
    
    # Verify API was called correctly
    mock_client.get.assert_called_once_with(
        "/api/v1/energy",
        params={"metric": "seu", "period": "week"}
    )
```

---

## Git Workflow

### Branch Naming

**Format:** `feature/{owner}-P{phase}-{type}{seq}-{short-description}`

**Examples:**
- `feature/lead-P1-L05-github-setup`
- `feature/emre-P1-E01-unit-tests`
- `feature/emre-P2-E10-turkish-locale`

**Components:**
- `{owner}`: `lead` or `emre`
- `{phase}`: Phase number (P1, P2, P3)
- `{type}`: `L` (Lead) or `E` (Emre)
- `{seq}`: Task sequence number

---

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(adapters): add RENERYO adapter` |
| `fix` | Bug fix | `fix(skill): handle missing metric gracefully` |
| `refactor` | Code improvement | `refactor(domain): extract response builder` |
| `test` | Add/update tests | `test(adapters): add integration tests` |
| `docs` | Documentation only | `docs(readme): update setup instructions` |
| `chore` | Build, dependencies | `chore(deps): upgrade ovos-workshop to 0.5` |

#### Scopes

Common scopes:
- `domain` - Domain models and business logic
- `adapters` - Adapter interface and implementations
- `skill` - OVOS skill handlers
- `web` - Web UI
- `services` - Support services (audit, settings)
- `devops` - Docker, CI/CD

#### Examples

✅ **GOOD commits:**
```
feat(adapters): implement RENERYOAdapter get_kpi method

- Add authentication with SettingsService
- Map RENERYO response to KPIResult
- Handle rate limiting with exponential backoff
- Add integration tests with mocked API

Closes P1-L04

───

fix(skill): handle unknown metric in kpi.energy intent

When user asks for unsupported metric, respond with fallback
dialog instead of crashing.

Fixes #42
```

❌ **BAD commits:**
```
fixed stuff
update
WIP
more changes
```

---

### Pull Request Workflow

1. **Create feature branch** from `main`
2. **Make changes** following standards in this guide
3. **Test locally** - all tests must pass
4. **Commit** with proper message format
5. **Push** to remote repository
6. **Create Pull Request** with description
7. **Address review comments** if any
8. **Merge** after approval

**Merge Strategies:**
- **Squash merge** - Emre's PRs (cleaner history)
- **Rebase merge** - Lead's PRs (preserves atomic commits)
- **Merge commit** - Large features with multiple developers

---

## Quick Reference

### DEC Compliance Checklist

Before committing code, check:

- [ ] **DEC-001:** No platform names in intent handlers or domain
- [ ] **DEC-002:** Using canonical metric names (not `seu`, `scrap_pct`)
- [ ] **DEC-003:** Domain models don't import from adapters
- [ ] **DEC-004:** All domain models have `frozen=True`
- [ ] **DEC-005:** Code works without config files (MockAdapter fallback)
- [ ] **DEC-006:** No hardcoded credentials, all via SettingsService
- [ ] **DEC-007:** Adapters only fetch data, intelligence in QueryDispatcher

---

### Code Quality Checklist

- [ ] Type hints on all parameters and return values
- [ ] Docstrings on all public functions
- [ ] Functions ≤20 lines
- [ ] Files ≤300 lines
- [ ] No bare `except:` clauses
- [ ] Proper import order (stdlib → third-party → local)
- [ ] Meaningful variable/function names (no abbreviations)

---

### Testing Checklist

- [ ] Test naming: `test_{function}_{scenario}_{expected}`
- [ ] AAA structure (Arrange-Act-Assert)
- [ ] Mocks for external dependencies
- [ ] Coverage ≥80% for new code
- [ ] All tests pass locally before PR

---

### Git Checklist

- [ ] Branch name: `feature/{owner}-P{phase}-{type}{seq}-{description}`
- [ ] Commit message: `<type>(<scope>): <subject>`
- [ ] Commit body explains WHY
- [ ] Task reference in footer: `Closes P1-E01`
- [ ] All tests passing
- [ ] No merge conflicts

---

## Resources

### Code Examples

All patterns demonstrated in this guide are implemented in the codebase:

- **Domain Models:** `skill/domain/models.py`, `skill/domain/results.py`
- **Adapters:** `skill/adapters/base.py`, `skill/adapters/mock.py`
- **Use Cases:** `skill/use_cases/query_dispatcher.py`
- **Intent Handlers:** `skill/__init__.py`
- **Tests:** `tests/` directory

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=skill --cov-report=html

# Run E2E tests
python test_e2e.py
```

### Getting Help

- **Questions about architecture:** Review this guide's Architecture Principles section
- **Code quality issues:** Check Code Quality Standards section
- **Test failures:** See Testing Standards section
- **Git workflow questions:** Refer to Git Workflow section

---

**Last Updated:** February 6, 2026  
**Maintained By:** AVAROS Development Team
