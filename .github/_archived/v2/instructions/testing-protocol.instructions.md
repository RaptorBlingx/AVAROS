---
applyTo: "**/tests/**,**/*_test.py,**/test_*.py"
---
# Testing Protocol

> **Purpose:** Testing standards, patterns, and templates for AVAROS project.

---

## Testing Philosophy

**Test Pyramid:**
```
        /\
       /  \      E2E Tests (10%)
      /────\     - Full voice interaction tests
     /      \    
    /────────\   Integration Tests (30%)
   /          \  - Adapter + API tests
  /────────────\ - Skill + QueryDispatcher tests
 /              \
/────────────────\ Unit Tests (60%)
                  - Domain models
                  - Business logic
                  - Pure functions
```

**Golden Rule:** Fast feedback loop. Unit tests run in <2 seconds.

---

## Coverage Requirements

| Code Type | Test Type | Coverage Target | Why |
|-----------|-----------|-----------------|-----|
| **Domain models** | Unit | 100% | Core business logic, no excuses |
| **Adapter implementations** | Integration (mocked API) | 90%+ | Critical data translation |
| **Use cases (QueryDispatcher)** | Unit (mocked adapters) | 95%+ | Orchestration logic must work |
| **Intent handlers** | Integration | 80%+ | Voice interaction paths |
| **Web endpoints** | API tests | 90%+ | User-facing functionality |
| **Utilities** | Unit | 90%+ | Shared code used everywhere |

---

## Test Naming Convention

### Format: `test_{function_name}_{scenario}_{expected_result}`

**Good names (self-documenting):**
```python
def test_get_kpi_with_valid_metric_returns_kpi_result():
def test_get_kpi_with_unknown_metric_raises_metric_not_found():
def test_get_kpi_with_api_timeout_raises_adapter_error():
def test_build_response_with_none_result_returns_error_dialog():
def test_create_adapter_with_no_config_returns_mock_adapter():
```

**Bad names (unclear):**
```python
def test_kpi():  # What about KPI?
def test_error():  # What error?
def test_1():  # What does this test?
def test_it_works():  # What works?
```

---

## Test Structure (Arrange-Act-Assert)

### Pattern: AAA (Arrange-Act-Assert)

```python
def test_get_kpi_with_valid_metric_returns_kpi_result():
    # ARRANGE: Set up test data and dependencies
    adapter = MockAdapter()
    dispatcher = QueryDispatcher(adapter)
    metric = "energy_per_unit"
    timeframe = TimeFrame.THIS_WEEK
    
    # ACT: Execute the function being tested
    result = dispatcher.get_kpi(metric, timeframe)
    
    # ASSERT: Verify the expected outcome
    assert isinstance(result, KPIResult)
    assert result.metric == "energy_per_unit"
    assert result.value > 0
    assert result.unit == "kWh/unit"
```

### Use Comments to Separate Sections

```python
def test_complex_scenario():
    # Arrange
    # ... setup code ...
    
    # Act
    # ... execution ...
    
    # Assert
    # ... verification ...
```

---

## Unit Test Patterns

### Testing Domain Models

```python
# tests/test_domain/test_models.py
from skill.domain.models import KPIResult
from datetime import datetime

def test_kpi_result_creation_with_valid_data_succeeds():
    # Arrange
    metric = "energy_per_unit"
    value = 45.2
    unit = "kWh/unit"
    timestamp = datetime.now()
    
    # Act
    result = KPIResult(
        metric=metric,
        value=value,
        unit=unit,
        timestamp=timestamp
    )
    
    # Assert
    assert result.metric == metric
    assert result.value == value
    assert result.unit == unit
    assert result.timestamp == timestamp

def test_kpi_result_is_immutable():
    # Arrange
    result = KPIResult(
        metric="energy_per_unit",
        value=45.2,
        unit="kWh/unit",
        timestamp=datetime.now()
    )
    
    # Act & Assert
    with pytest.raises(FrozenInstanceError):
        result.value = 50.0  # Should fail

def test_kpi_result_with_negative_value_raises_error():
    # Act & Assert
    with pytest.raises(ValueError, match="value cannot be negative"):
        KPIResult(
            metric="energy_per_unit",
            value=-10.0,  # Invalid
            unit="kWh/unit",
            timestamp=datetime.now()
        )
```

### Testing Pure Functions

```python
# tests/test_services/test_response_builder.py
from skill.services.response_builder import build_kpi_response

def test_build_kpi_response_with_valid_result_returns_formatted_string():
    # Arrange
    result = KPIResult(
        metric="energy_per_unit",
        value=45.2,
        unit="kWh/unit",
        timestamp=datetime.now()
    )
    
    # Act
    response = build_kpi_response(result)
    
    # Assert
    assert "45.2" in response
    assert "kWh/unit" in response
    assert "energy per unit" in response.lower()

def test_build_kpi_response_with_none_result_returns_error_message():
    # Act
    response = build_kpi_response(None)
    
    # Assert
    assert "not available" in response.lower() or "error" in response.lower()
```

---

## Mocking Patterns

### Using unittest.mock

```python
from unittest.mock import Mock, patch, MagicMock

def test_adapter_calls_api_with_correct_params():
    # Arrange
    mock_client = Mock()
    mock_client.get.return_value = {
        "seu": 45.2,
        "unit": "kWh/unit",
        "timestamp": "2026-02-04T10:00:00Z"
    }
    
    adapter = RENERYOAdapter(client=mock_client)
    
    # Act
    result = adapter.get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
    
    # Assert
    mock_client.get.assert_called_once_with(
        "/api/v1/energy/seu",
        params={"period": "week"}
    )
    assert result.value == 45.2
```

### Mocking Async Functions

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_query_dispatcher_calls_prevention_service():
    # Arrange
    mock_adapter = Mock()
    mock_adapter.get_kpi.return_value = KPIResult(...)
    
    mock_prevention = AsyncMock()
    mock_prevention.check_anomaly.return_value = None  # No anomaly
    
    dispatcher = QueryDispatcher(
        adapter=mock_adapter,
        prevention=mock_prevention
    )
    
    # Act
    await dispatcher.get_kpi_with_context("energy_per_unit")
    
    # Assert
    mock_prevention.check_anomaly.assert_called_once()
```

### Patching External Dependencies

```python
@patch('skill.adapters.reneryo.requests.get')
def test_reneryo_adapter_handles_api_timeout(mock_get):
    # Arrange
    mock_get.side_effect = requests.Timeout("API timeout")
    adapter = RENERYOAdapter()
    
    # Act & Assert
    with pytest.raises(AdapterError, match="timeout"):
        adapter.get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
```

---

## Integration Test Patterns

### Testing Adapters with Mocked HTTP

```python
# tests/test_adapters/test_reneryo_adapter.py
import responses
from skill.adapters.reneryo import RENERYOAdapter

@responses.activate
def test_reneryo_adapter_maps_response_correctly():
    # Arrange
    responses.add(
        responses.GET,
        "https://api.reneryo.com/v1/metrics/seu",
        json={
            "seu": 45.2,
            "unit": "kWh/piece",
            "timestamp": "2026-02-04T10:00:00Z",
            "confidence": 0.95
        },
        status=200
    )
    
    adapter = RENERYOAdapter(base_url="https://api.reneryo.com")
    
    # Act
    result = adapter.get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
    
    # Assert
    assert result.metric == "energy_per_unit"  # Canonical name
    assert result.value == 45.2
    assert result.unit == "kWh/unit"  # Canonical unit
    assert result.metadata["confidence"] == 0.95

@responses.activate
def test_reneryo_adapter_handles_404_error():
    # Arrange
    responses.add(
        responses.GET,
        "https://api.reneryo.com/v1/metrics/seu",
        json={"error": "Metric not found"},
        status=404
    )
    
    adapter = RENERYOAdapter(base_url="https://api.reneryo.com")
    
    # Act & Assert
    with pytest.raises(MetricNotFoundError):
        adapter.get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
```

### Testing OVOS Intent Handlers

```python
# tests/test_skill_handlers.py
from ovos_workshop.skills.base import OVOSSkill
from skill import AvarosSkill

def test_handle_kpi_energy_with_valid_query_speaks_result(mock_skill):
    # Arrange
    skill = AvarosSkill()
    skill.query_dispatcher = Mock()
    skill.query_dispatcher.get_kpi.return_value = KPIResult(
        metric="energy_per_unit",
        value=45.2,
        unit="kWh/unit",
        timestamp=datetime.now()
    )
    
    message = Mock()
    message.data = {}
    
    # Act
    skill.handle_kpi_energy(message)
    
    # Assert
    skill.speak_dialog.assert_called_once()
    call_args = skill.speak_dialog.call_args
    assert "45.2" in str(call_args)
    assert "kWh/unit" in str(call_args)
```

---

## Fixture Patterns (pytest)

### Reusable Test Data

```python
# tests/conftest.py
import pytest
from datetime import datetime
from skill.domain.models import KPIResult

@pytest.fixture
def sample_kpi_result():
    """Reusable KPI result for tests."""
    return KPIResult(
        metric="energy_per_unit",
        value=45.2,
        unit="kWh/unit",
        timestamp=datetime(2026, 2, 4, 10, 0, 0)
    )

@pytest.fixture
def mock_adapter():
    """Reusable mock adapter."""
    adapter = Mock(spec=ManufacturingAdapter)
    adapter.get_kpi.return_value = KPIResult(
        metric="energy_per_unit",
        value=45.2,
        unit="kWh/unit",
        timestamp=datetime.now()
    )
    return adapter
```

Usage:
```python
def test_something(sample_kpi_result, mock_adapter):
    # Use fixtures directly as parameters
    dispatcher = QueryDispatcher(mock_adapter)
    result = dispatcher.get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
    assert result == sample_kpi_result
```

### Parametrized Tests

```python
@pytest.mark.parametrize("metric,expected_unit", [
    ("energy_per_unit", "kWh/unit"),
    ("scrap_rate", "%"),
    ("oee", "%"),
    ("co2_per_unit", "kg CO2/unit"),
])
def test_adapter_returns_correct_unit_for_metric(metric, expected_unit):
    # Arrange
    adapter = MockAdapter()
    
    # Act
    result = adapter.get_kpi(metric, TimeFrame.THIS_WEEK)
    
    # Assert
    assert result.unit == expected_unit
```

---

## Test Organization

### File Structure

```
tests/
├── conftest.py                      # Shared fixtures
├── requirements-test.txt            # Test dependencies
│
├── test_domain/
│   ├── __init__.py
│   ├── test_models.py              # Domain model tests (100% coverage)
│   └── test_exceptions.py          # Exception hierarchy tests
│
├── test_adapters/
│   ├── __init__.py
│   ├── test_mock_adapter.py        # MockAdapter tests
│   ├── test_reneryo_adapter.py     # RENERYO integration tests
│   └── test_adapter_factory.py     # Factory pattern tests
│
├── test_use_cases/
│   ├── __init__.py
│   └── test_query_dispatcher.py    # QueryDispatcher orchestration tests
│
├── test_skill/
│   ├── __init__.py
│   └── test_intent_handlers.py     # OVOS intent handler tests
│
└── test_services/
    ├── __init__.py
    ├── test_response_builder.py    # Response formatting tests
    └── test_settings_service.py    # Settings management tests
```

### Naming Convention

- **File:** `test_{module_name}.py`
- **Class:** `Test{ClassName}` (optional, for grouping)
- **Function:** `test_{function}_{scenario}_{expected}`

---

## Running Tests

### Local Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=skill --cov-report=html

# Run specific file
pytest tests/test_domain/test_models.py

# Run specific test
pytest tests/test_domain/test_models.py::test_kpi_result_creation_with_valid_data_succeeds

# Run tests matching pattern
pytest -k "adapter"

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### CI/CD (Docker)

```bash
# Run in Docker container
docker compose run --rm avaros pytest

# With coverage
docker compose run --rm avaros pytest --cov=skill --cov-report=term-missing
```

---

## Test Templates

### Template: Unit Test for Domain Model

```python
from skill.domain.models import YourModel
import pytest

def test_your_model_creation_with_valid_data_succeeds():
    # Arrange
    param1 = "value1"
    param2 = 42
    
    # Act
    model = YourModel(param1=param1, param2=param2)
    
    # Assert
    assert model.param1 == param1
    assert model.param2 == param2

def test_your_model_is_immutable():
    # Arrange
    model = YourModel(param1="value1", param2=42)
    
    # Act & Assert
    with pytest.raises(FrozenInstanceError):
        model.param1 = "new_value"

def test_your_model_with_invalid_data_raises_error():
    # Act & Assert
    with pytest.raises(ValueError, match="param2 must be positive"):
        YourModel(param1="value1", param2=-1)
```

### Template: Integration Test for Adapter

```python
import responses
from skill.adapters.your_adapter import YourAdapter

@responses.activate
def test_your_adapter_maps_response_correctly():
    # Arrange
    responses.add(
        responses.GET,
        "https://api.platform.com/endpoint",
        json={"platform_field": "value"},
        status=200
    )
    
    adapter = YourAdapter()
    
    # Act
    result = adapter.get_kpi("canonical_metric", TimeFrame.THIS_WEEK)
    
    # Assert
    assert result.metric == "canonical_metric"
    assert result.value == expected_value

@responses.activate
def test_your_adapter_handles_api_error():
    # Arrange
    responses.add(
        responses.GET,
        "https://api.platform.com/endpoint",
        json={"error": "Something went wrong"},
        status=500
    )
    
    adapter = YourAdapter()
    
    # Act & Assert
    with pytest.raises(AdapterError):
        adapter.get_kpi("canonical_metric", TimeFrame.THIS_WEEK)
```

### Template: Test with Mocked Dependencies

```python
from unittest.mock import Mock
from skill.use_cases.query_dispatcher import QueryDispatcher

def test_query_dispatcher_with_valid_metric_returns_result():
    # Arrange
    mock_adapter = Mock()
    mock_adapter.get_kpi.return_value = KPIResult(
        metric="energy_per_unit",
        value=45.2,
        unit="kWh/unit",
        timestamp=datetime.now()
    )
    
    dispatcher = QueryDispatcher(adapter=mock_adapter)
    
    # Act
    result = dispatcher.get_kpi("energy_per_unit", TimeFrame.THIS_WEEK)
    
    # Assert
    mock_adapter.get_kpi.assert_called_once_with(
        "energy_per_unit",
        TimeFrame.THIS_WEEK
    )
    assert result.value == 45.2
```

---

## Common Testing Mistakes

### ❌ Testing Implementation Instead of Behavior

```python
# BAD: Testing how it works internally
def test_uses_correct_algorithm():
    result = calculate_oee()
    assert result.used_bubble_sort  # Who cares HOW?

# GOOD: Testing what it produces
def test_calculate_oee_with_valid_data_returns_correct_value():
    result = calculate_oee(availability=0.9, performance=0.95, quality=0.98)
    assert result == 0.84
```

### ❌ Tests That Don't Test Anything

```python
# BAD: Doesn't verify behavior
def test_get_kpi():
    result = get_kpi("energy_per_unit")
    assert result  # What about the result?

# GOOD: Verifies specific behavior
def test_get_kpi_returns_positive_value():
    result = get_kpi("energy_per_unit")
    assert result.value > 0
    assert result.unit == "kWh/unit"
```

### ❌ Overmocking

```python
# BAD: Mocking everything, including the thing being tested
def test_query_dispatcher():
    mock_dispatcher = Mock()
    mock_dispatcher.get_kpi.return_value = KPIResult(...)
    result = mock_dispatcher.get_kpi("energy_per_unit")
    assert result  # You're testing the mock, not the real code!

# GOOD: Only mock external dependencies
def test_query_dispatcher():
    mock_adapter = Mock()  # External dependency
    dispatcher = QueryDispatcher(mock_adapter)  # Real code
    result = dispatcher.get_kpi("energy_per_unit")
```

---

## Test-Driven Development (TDD)

### Red-Green-Refactor Cycle

1. **RED:** Write a failing test
```python
def test_get_kpi_with_unknown_metric_raises_error():
    with pytest.raises(MetricNotFoundError):
        get_kpi("invalid_metric")
```

2. **GREEN:** Make it pass (simplest way)
```python
def get_kpi(metric: str) -> KPIResult:
    if metric not in SUPPORTED_METRICS:
        raise MetricNotFoundError(metric)
    # ... rest of implementation
```

3. **REFACTOR:** Improve code quality
```python
def get_kpi(metric: str) -> KPIResult:
    validate_metric(metric)  # Extracted to function
    # ... rest of implementation
```

---

## How Agents Use This File

**@lead-dev agent:**
- Writes tests alongside production code
- Uses test templates from this file
- Follows AAA pattern

**@quality agent:**
- Verifies test coverage meets targets
- Checks test quality (not just quantity)
- Ensures tests actually test behavior

**@pr-review agent:**
- Checks if Emre added tests for new code
- Verifies test naming follows convention
- Teaches Emre good testing practices
