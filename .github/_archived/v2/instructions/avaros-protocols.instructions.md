---
applyTo: "**"
---
# AVAROS Development Protocols

> **Purpose:** High standards that ALL agents and developers follow. These are not bureaucracy — just best practices codified.

---

## Protocol 1: Architecture Compliance (DEC-001 to DEC-007)

Every code change MUST comply with these Design Decisions:

| DEC | Rule | Violation Example | Compliant Example |
|-----|------|-------------------|-------------------|
| **DEC-001** | Platform-Agnostic Design | `skill/__init__.py` imports `RENERYOAdapter` directly | Intent handler calls `QueryDispatcher`, which uses adapter interface |
| **DEC-002** | Universal Metric Framework | Using `reneryo_energy_seu` in intent handler | Using canonical `energy_per_unit` metric |
| **DEC-003** | Clean Architecture | `skill/domain/models.py` imports from `skill/adapters/` | Domain never imports from infrastructure layers |
| **DEC-004** | Immutable Domain Models | `@dataclass` without `frozen=True` | `@dataclass(frozen=True)` for all domain models |
| **DEC-005** | Zero-Config First Run | Skill fails if `config.yaml` missing | MockAdapter works out-of-box, config optional |
| **DEC-006** | Settings Service Pattern | `os.environ['API_KEY']` in adapter | `SettingsService.get_platform_config()` |
| **DEC-007** | Intelligence in Orchestration | `adapter.check_anomaly()` method | `QueryDispatcher` calls PREVENTION service, adapter only fetches data |

**Enforcement:** All agents check code changes against this table before committing.

---

## Protocol 2: Code Quality Standards

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

**No abbreviations** except well-known terms:
- ✅ OK: `API`, `KPI`, `OEE`, `ID`, `HTTP`, `JSON`
- ❌ Avoid: `mgr`, `cfg`, `tmp`, `res`, `req`

### Function Standards

**Max 20 lines per function** - Extract helper functions if longer
```python
# ❌ BAD: 50-line function doing too much
def process_kpi_request(utterance, context, settings):
    # ... 50 lines of parsing, validation, API calls, formatting ...

# ✅ GOOD: Split into focused functions
def process_kpi_request(utterance: str, context: dict) -> str:
    metric = extract_metric(utterance)
    timeframe = extract_timeframe(utterance)
    result = fetch_kpi(metric, timeframe)
    return format_response(result)
```

**Single Responsibility** - One reason to change
```python
# ❌ BAD: Function does parsing AND validation AND API call
def get_data(text):
    metric = parse_utterance(text)
    if not is_valid(metric):
        raise ValueError
    return call_api(metric)

# ✅ GOOD: Separate concerns
def parse_metric(utterance: str) -> str:
    """Extract metric name from utterance."""
    # parsing logic only

def fetch_kpi(metric: str) -> KPIResult:
    """Fetch KPI from adapter."""
    # API logic only
```

**Type hints MANDATORY**
```python
# ❌ BAD: No type hints
def get_kpi(metric, timeframe):
    return adapter.fetch(metric, timeframe)

# ✅ GOOD: Complete type hints
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

**Docstrings Required** for all public functions
- Args: Parameter descriptions
- Returns: What the function returns
- Raises: What exceptions it can raise

### File Standards

**Max 300 lines** - Split into modules if longer
```
# ❌ BAD: 800-line god file
skill/adapters/reneryo.py  # Everything in one file

# ✅ GOOD: Modular structure
skill/adapters/reneryo/
    __init__.py
    client.py          # HTTP client (100 lines)
    mapper.py          # Response mapping (120 lines)
    auth.py            # Authentication (80 lines)
```

**One class per file** (except small related classes)
```python
# ❌ BAD: Multiple unrelated classes
# skill/domain/models.py
class KPIResult: ...
class UserSettings: ...
class AuditLog: ...

# ✅ GOOD: One primary class per file
# skill/domain/results.py
class KPIResult: ...

# skill/domain/settings.py
class UserSettings: ...

# skill/services/audit.py
class AuditLog: ...
```

**Import order** (with blank lines between groups)
```python
# Standard library
import json
import logging
from datetime import datetime
from typing import Optional

# Third-party
import aiohttp
from ovos_workshop.decorators import intent_handler

# Local
from skill.domain.models import KPIResult
from skill.adapters.base import ManufacturingAdapter
```

### Error Handling

**Never catch bare `except:`**
```python
# ❌ BAD: Catches everything, even KeyboardInterrupt
try:
    result = adapter.get_kpi(metric)
except:
    return None

# ✅ GOOD: Specific exception handling
try:
    result = adapter.get_kpi(metric)
except MetricNotFoundError:
    logger.warning(f"Metric not found: {metric}")
    raise
except AdapterError as e:
    logger.error(f"Adapter failed: {e}", exc_info=True)
    raise
```

**Custom exceptions inherit from `AvarosError`**
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

**Log with context, then re-raise or return Result type**
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

## Protocol 3: Testing Requirements

| Code Type | Test Requirement | Coverage Target |
|-----------|------------------|-----------------|
| Domain models | Unit tests | 100% |
| Adapter implementations | Integration tests with mocked API | 90%+ |
| Use cases (QueryDispatcher) | Unit tests with mocked adapters | 95%+ |
| Intent handlers | Integration tests with test utterances | 80%+ |
| Web endpoints | API tests with test client | 90%+ |

### Test Naming Convention

Format: `test_{function_name}_{scenario}_{expected_result}`

```python
# Good test names (self-documenting)
def test_get_kpi_with_valid_metric_returns_kpi_result():
def test_get_kpi_with_unknown_metric_raises_metric_not_found():
def test_get_kpi_with_api_timeout_raises_adapter_error():
def test_build_response_with_none_result_returns_error_dialog():
```

### Test Structure (Arrange-Act-Assert)

```python
def test_get_kpi_with_valid_metric_returns_kpi_result():
    # Arrange
    adapter = MockAdapter()
    dispatcher = QueryDispatcher(adapter)
    metric = "energy_per_unit"
    
    # Act
    result = dispatcher.get_kpi(metric, TimeFrame.THIS_WEEK)
    
    # Assert
    assert isinstance(result, KPIResult)
    assert result.metric == "energy_per_unit"
    assert result.value > 0
```

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

## Protocol 4: Documentation Requirements

### Code Documentation

**Every public function** has a docstring:
```python
def get_kpi(metric: str, timeframe: TimeFrame) -> KPIResult:
    """Fetch KPI value for given metric and timeframe.
    
    Args:
        metric: Canonical metric name from Universal Metric Framework
        timeframe: Time period for aggregation
        
    Returns:
        KPIResult containing value, unit, timestamp, and metadata
        
    Raises:
        MetricNotFoundError: Metric not supported by current adapter
        AdapterError: Platform API communication failed
        
    Example:
        >>> result = get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
        >>> print(f"{result.value} {result.unit}")
        45.2 kWh/unit
    """
```

**Complex logic** has inline comments explaining WHY:
```python
# Good: Explains the reasoning
# Use exponential backoff because RENERYO rate limits at 100 req/min
for attempt in range(MAX_RETRIES):
    time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s
    try:
        return self._call_api()
    except RateLimitError:
        continue

# Bad: States the obvious
# Loop 3 times
for i in range(3):
    ...
```

**TODO comments** include phase reference:
```python
# TODO PHASE 2: Integrate with DocuBoT for document grounding
# TODO PHASE 3: Add PREVENTION service for anomaly detection
# FIXME: This assumes UTC timezone, should use platform timezone
```

### Architecture Documentation

**New design decisions** → Add to `DECISIONS.md`:
```markdown
### DEC-008: PostgreSQL over SQLite (2026-02-04)
**Context:** SettingsService needs database backend
**Decision:** Use PostgreSQL from day one
**Rationale:** Production-grade, supports concurrent connections
**Status:** ACTIVE
```

**Breaking changes** → Update `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`:
- If you change adapter interface, update the architecture doc
- If you add/remove a DEC principle, update both docs

---

## Protocol 5: Commit Message Standards

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(adapters): add RENERYO adapter` |
| `fix` | Bug fix | `fix(skill): handle missing metric gracefully` |
| `refactor` | Code improvement without behavior change | `refactor(domain): extract response builder` |
| `test` | Add/update tests | `test(adapters): add integration tests` |
| `docs` | Documentation only | `docs(readme): update setup instructions` |
| `chore` | Build, dependencies, etc. | `chore(deps): upgrade ovos-workshop to 0.5` |

### Scopes

Common scopes in AVAROS:
- `domain` - Domain models and business logic
- `adapters` - Adapter interface and implementations
- `skill` - OVOS skill handlers
- `web` - Web UI
- `services` - Support services (audit, settings)
- `devops` - Docker, CI/CD

### Examples

**Good commits:**
```
feat(adapters): implement RENERYOAdapter get_kpi method

- Add authentication with SettingsService
- Map RENERYO response to KPIResult
- Handle rate limiting with exponential backoff
- Add integration tests with mocked API

Closes P1-L01

───

fix(skill): handle unknown metric in kpi.energy intent

When user asks for unsupported metric, respond with fallback
dialog instead of crashing.

Fixes #42

───

refactor(domain): make KPIResult immutable (DEC-004)

- Add frozen=True to dataclass
- Add unsafe_hash=True for set usage
- Update tests to not mutate results

Closes P1-L03
```

**Bad commits:**
```
fixed stuff
update
WIP
asdf
more changes
```

### Task ID Reference

Always include task ID in footer:
```
Closes P1-L01
Closes P1-E05
Part of P2-L03
```

---

## Task Breakdown Conventions

### Task Granularity: 1-2 Days

**Good task size:**
- P1-L01: Implement domain models (1 day)
- P1-L02: Create adapter interface (1 day)
- P1-E05: Build React KPI component (1.5 days)

**Too small (combine these):**
- Add type hints to one function (15 min)
- Fix typo in docstring (5 min)

**Too large (break down):**
- Implement entire Phase 2 (weeks)
- Build complete web UI (days)

### Task ID Assignment Rules

**Lead Developer tasks:** `P{phase}-L{seq}`
- Domain layer: P1-L01, P1-L02, ...
- Adapter interface: P1-L03
- Adapter implementations: P1-L04, P2-L01, ...
- QueryDispatcher: P1-L05, P2-L02, ...
- Security/audit: P1-L06, P3-L01, ...

**Emre (Junior) tasks:** `P{phase}-E{seq}`
- Web UI: P1-E01, P1-E02, ...
- Intent handlers: P1-E05, P1-E06, ...
- Dialogs: P1-E10, P1-E11, ...
- Tests (for his code): P1-E15, ...
- Docker: P1-E20, P2-E05, ...

### Dependency Tracking

Tasks with dependencies:
```markdown
| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P1-L04 | Implement QueryDispatcher | 🔄 IN PROGRESS | P1-L02 ✅, P1-L03 ✅ |
| P1-E05 | Build API endpoint | ⬜ TODO | P1-L04 |
```

Block tasks explicitly:
```markdown
| P1-E05 | Build API endpoint | ⚠️ BLOCKED | P1-L04 (in progress) |
```

---

## AVAROS-Specific Patterns

### Universal Metric Names

Always use canonical names from Universal Metric Framework:

| Category | Canonical Metrics |
|----------|------------------|
| **Energy** | `energy_per_unit`, `energy_total`, `peak_demand`, `peak_tariff_exposure` |
| **Material** | `scrap_rate`, `rework_rate`, `material_efficiency`, `recycled_content` |
| **Supplier** | `supplier_lead_time`, `supplier_defect_rate`, `supplier_on_time`, `supplier_co2_per_kg` |
| **Production** | `oee`, `throughput`, `cycle_time`, `changeover_time` |
| **Carbon** | `co2_per_unit`, `co2_total`, `co2_per_batch` |

### Intent Naming Convention

Format: `{query_type}.{domain}.{detail}.intent`

```
kpi.energy.per_unit.intent        # "What's our energy per unit?"
compare.supplier.performance.intent  # "Compare Supplier A and B"
trend.scrap.monthly.intent        # "Show scrap trend last 3 months"
anomaly.production.check.intent   # "Any unusual patterns?"
whatif.material.substitute.intent # "What if we use recycled plastic?"
```

### Adapter Response Mapping

Platform responses MUST be mapped to canonical format:

```python
# ❌ BAD: Exposing platform-specific format
def get_kpi(self, metric: str) -> dict:
    return self._api_client.get(f"/reneryo/{metric}")

# ✅ GOOD: Map to canonical KPIResult
def get_kpi(self, metric: str) -> KPIResult:
    response = self._api_client.get(f"/reneryo/{metric}")
    return KPIResult(
        metric=metric,  # Canonical name
        value=response["seu"],  # Extract value
        unit="kWh/unit",  # Canonical unit
        timestamp=parse_datetime(response["ts"]),
        metadata={"source": "RENERYO", "confidence": response.get("conf")}
    )
```

---

## Summary

**These protocols are NOT optional.** Every agent and developer follows them.

**Enforcement:**
- @quality agent reviews ALL code against these protocols
- @pr-review agent checks Emre's PRs for protocol compliance
- @planner agent uses these conventions for task breakdown

**Reference this file** when:
- Writing new code
- Reviewing code
- Creating tasks
- Making architectural decisions
- Writing commit messages
