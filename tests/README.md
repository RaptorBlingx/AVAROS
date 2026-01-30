# AVAROS Test Suite

## Overview

Comprehensive test suite for AVAROS OVOS skill, implementing Sprint 1 testing tasks:

- **T4**: QueryDispatcher unit tests
- **T5**: Result type validation tests
- **T6**: Exception hierarchy tests
- **T7**: AdapterFactory tests
- **T8**: SettingsService tests
- **T9**: Basic skill handler tests

## Test Structure

```
tests/
├── __init__.py                    # Test suite initialization
├── conftest.py                    # Shared fixtures and configuration
├── test_query_dispatcher.py       # T4: QueryDispatcher routing tests
├── test_result_types.py           # T5: Canonical data model tests
├── test_exceptions.py             # T6: Exception hierarchy tests
├── test_adapter_factory.py        # T7: Adapter factory tests
├── test_settings_service.py       # T8: Settings management tests
├── test_skill_handlers.py         # T9: OVOS intent handler tests
├── requirements-test.txt          # Test dependencies
└── README.md                      # This file
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r tests/requirements-test.txt
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
# T4: QueryDispatcher tests
pytest tests/test_query_dispatcher.py

# T5: Result type tests
pytest tests/test_result_types.py

# T6: Exception tests
pytest tests/test_exceptions.py

# T7: AdapterFactory tests
pytest tests/test_adapter_factory.py

# T8: SettingsService tests
pytest tests/test_settings_service.py

# T9: Skill handler tests
pytest tests/test_skill_handlers.py
```

### Run with Coverage

```bash
pytest tests/ --cov=skill --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`

### Run in Parallel

```bash
pytest tests/ -n auto
```

### Run Specific Test Class

```bash
pytest tests/test_query_dispatcher.py::TestQueryDispatcherKPI
```

### Run Specific Test

```bash
pytest tests/test_query_dispatcher.py::TestQueryDispatcherKPI::test_get_kpi_routes_correctly
```

## Test Coverage Goals

| Component | Target Coverage | Status |
|-----------|----------------|--------|
| QueryDispatcher | 90%+ | ✅ |
| Result Types | 95%+ | ✅ |
| Exceptions | 95%+ | ✅ |
| AdapterFactory | 85%+ | ✅ |
| SettingsService | 85%+ | ✅ |
| Skill Handlers | 80%+ | ✅ |

## Test Categories

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Fast execution
- All tests in this suite are unit tests

### Integration Tests
- Test component interactions
- Use real adapters (MockAdapter)
- Moderate execution time
- To be added in Sprint 2

### Contract Tests
- Verify adapter interface compliance
- Ensure all adapters implement ManufacturingAdapter
- Included in `test_adapter_factory.py`

## Test Fixtures

Common fixtures are defined in `conftest.py`:

- `mock_config` - Sample configuration dictionary
- `mock_kpi_data` - Sample KPI response data
- `mock_trend_data` - Sample trend response data
- `mock_comparison_data` - Sample comparison data
- `mock_anomaly_data` - Sample anomaly data
- `mock_whatif_data` - Sample what-if scenario data

## Testing Principles

### SOLID Compliance
Tests verify that components follow SOLID principles:
- Single Responsibility
- Open/Closed
- Liskov Substitution
- Interface Segregation
- Dependency Inversion

### Clean Architecture
Tests ensure proper layer separation:
- Domain layer has no external dependencies
- Adapters implement abstract interfaces
- Infrastructure depends on domain, not vice versa

### Platform-Agnostic Design
Tests verify:
- Intent handlers use canonical metrics
- No platform-specific code in skill
- Adapters translate to/from canonical types

## Key Test Scenarios

### T4: QueryDispatcher Tests
- ✅ Routes GET_KPI queries to adapter.get_kpi()
- ✅ Routes COMPARE queries to adapter.compare()
- ✅ Routes TREND queries to adapter.get_trend()
- ✅ Routes ANOMALY queries to adapter.check_anomaly()
- ✅ Routes WHATIF queries to adapter.simulate_whatif()
- ✅ Propagates errors correctly

### T5: Result Type Tests
- ✅ All result types are immutable (frozen dataclasses)
- ✅ All result types support from_dict() deserialization
- ✅ CanonicalMetric enum has all required metrics
- ✅ Field validation and type checking
- ✅ Proper datetime handling

### T6: Exception Tests
- ✅ All exceptions inherit from AVAROSError
- ✅ Structured error information (code, message, details)
- ✅ Exception serialization (to_dict())
- ✅ Specific exception types (Adapter, Validation, Config, Query, Data)
- ✅ Error context preservation

### T7: AdapterFactory Tests
- ✅ Creates adapters by platform type
- ✅ Adapter registration system
- ✅ Hot-reload on configuration change
- ✅ Interface compliance verification
- ✅ Configuration passing to adapters

### T8: SettingsService Tests
- ✅ Database-backed configuration
- ✅ Platform config validation
- ✅ Alert threshold management
- ✅ First-run detection
- ✅ Observer pattern for hot-reload
- ✅ Settings caching

### T9: Skill Handler Tests
- ✅ Intent routing to QueryDispatcher
- ✅ Slot extraction from messages
- ✅ Dialog response generation
- ✅ Error handling in all handlers
- ✅ Default value handling
- ✅ Missing slot detection

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

```yaml
# Example CI configuration
test:
  script:
    - pip install -r tests/requirements-test.txt
    - pytest tests/ --cov=skill --cov-report=xml
    - pytest tests/ --junitxml=test-results.xml
```

## Code Quality Checks

### Type Checking

```bash
mypy skill/ --strict
```

### Linting

```bash
flake8 skill/ tests/
```

### Code Formatting

```bash
black skill/ tests/ --check
```

## Mock Implementations

Tests include mock implementations for:

- **MockAdapter**: Implements ManufacturingAdapter with hardcoded responses
- **RENERYOAdapter**: Mock RENERYO platform adapter
- **MockDatabase**: In-memory database for SettingsService tests
- **MockOVOSSkill**: Base skill class mock
- **Message**: OVOS message mock

These mocks follow the same interfaces as real implementations, ensuring tests accurately reflect production behavior.

## Async Testing

All async handlers use `pytest-asyncio`:

```python
@pytest.mark.asyncio
async def test_async_handler(skill):
    await skill.handle_kpi_intent(message)
```

## Test Naming Convention

Tests follow the pattern:
- `test_<component>_<scenario>_<expected_result>`

Examples:
- `test_get_kpi_routes_correctly`
- `test_adapter_error_propagation`
- `test_settings_validation_missing_field`

## Next Steps

### Sprint 2 Testing Tasks
- Integration tests with MockAdapter
- End-to-end voice intent tests
- Performance benchmarks
- Load testing for concurrent queries
- DocuBoT integration tests
- PREVENTION integration tests

### Test Enhancements
- Property-based testing with Hypothesis
- Mutation testing with mutmut
- Contract testing with Pact
- Snapshot testing for responses

## Contributing

When adding new code:
1. Write tests first (TDD)
2. Aim for 80%+ coverage
3. Include positive and negative test cases
4. Test error handling
5. Use descriptive test names
6. Add docstrings to test classes

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [AVAROS Architecture](../docs/ARCHITECTURE.md)
- [AVAROS Coding Standards](../.github/instructions/code-quality.instructions.md)
