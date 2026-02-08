## Task: [P1-E02] Write Unit Tests for Domain Result Types

**Story Points:** 3
**Dependencies:** P1-E01 (onboarding complete), P1-L08 (fake tests rewritten — so you don't conflict)
**Branch:** `feature/emre-P1-E02-domain-results-tests`

### Objective
Write comprehensive unit tests for all 5 result types in `skill/domain/results.py` (KPIResult, ComparisonResult, TrendResult, AnomalyResult, WhatIfResult). These are the canonical output types that every adapter must produce and every handler consumes. 100% coverage of this module is the goal.

### Requirements
- [ ] Create `tests/test_domain/test_results.py` with tests for all 5 result types
- [ ] Import REAL classes from `skill.domain.results` — never redefine models locally
- [ ] Test construction with valid data
- [ ] Test immutability (`frozen=True`) — assigning to fields should raise `FrozenInstanceError`
- [ ] Test `to_dict()` serialization for each result type
- [ ] Test `formatted_value` property on KPIResult
- [ ] Test edge cases: zero values, empty strings, boundary conditions
- [ ] Test ComparisonResult with 2+ assets
- [ ] Test TrendResult direction logic (up/down/stable)
- [ ] Test AnomalyResult with and without anomalies
- [ ] Test WhatIfResult delta calculations

### Acceptance Criteria
- [ ] All tests pass: `pytest tests/test_domain/test_results.py -v`
- [ ] Coverage of `skill/domain/results.py` ≥ 95% (run `pytest --cov=skill.domain.results tests/test_domain/test_results.py`)
- [ ] All tests import from `skill.domain.results` and `skill.domain.models` — zero local class redefinitions
- [ ] Tests follow AAA pattern (Arrange → Act → Assert)
- [ ] Test names follow convention: `test_{method}_{scenario}_{expected}`
- [ ] No lint errors

### Files to Create/Modify
- `tests/test_domain/test_results.py` — **Create new**. All result type tests go here.
- Do NOT modify `tests/test_domain/test_models.py` — that file already has good tests

### Testing Requirements
- Run tests in isolation: `pytest tests/test_domain/test_results.py -v`
- Run full suite to check no regressions: `pytest tests/ -v`
- Check coverage: `pytest --cov=skill.domain.results tests/test_domain/test_results.py --cov-report=term-missing`
- Target: ≥ 95% coverage of results.py

### Reference
- `skill/domain/results.py` — the module under test (read ALL 367 lines carefully)
- `skill/domain/models.py` — imports you'll need (CanonicalMetric, TimePeriod, DataPoint, Anomaly)
- `tests/test_domain/test_models.py` — example of GOOD test style (imports real classes, AAA pattern)
- `DEVELOPMENT.md` L779–L983 for testing standards
- `.github/instructions/coding-standards.instructions.md` for quick checklist

### Notes
- **Wait for P1-L08 to merge before starting.** Lead is rewriting the old fake test files. Starting before that merges could cause git conflicts.
- Look at `tests/test_domain/test_models.py` for the correct test style — it imports real classes and follows AAA pattern. Your tests should look similar.
- The result types depend on domain models (CanonicalMetric, TimePeriod, etc.). Use the fixtures in `tests/conftest.py` if any exist, or create your own test data.
- Each result type has different fields and methods. Read `results.py` carefully before writing tests.
- `KPIResult.formatted_value` is a property — make sure to test it with different metric types (%, kWh, etc.)
- `ComparisonResult` has a `winner_id` and `difference` — test with various asset combinations.
- `TrendResult` has `direction` and `change_percent` — test all 3 directions (up, down, stable).
- Keep tests focused. One test class per result type, meaningful test method names.
