# Task P1-E01: Add Unit Tests for Existing Code

## 🎯 Objective
Write tests for domain models, adapters, and query dispatcher.
Target: 80%+ coverage on existing code. Learn the codebase through testing.

## 📋 Requirements

### Test Files to Create/Extend
- [ ] `tests/test_domain/test_models.py` — All domain model creation + validation
- [ ] `tests/test_adapters/test_mock.py` — MockAdapter returns valid KPIResult
- [ ] `tests/test_use_cases/test_query_dispatcher.py` — All 5 query types

### Testing Standards
- [ ] AAA pattern (Arrange-Act-Assert)
- [ ] Naming: `test_{method}_{scenario}_{expected}`
- [ ] Use `conftest.py` fixtures (don't repeat setup)

## 📐 Protocols & Standards
- `.github/instructions/testing-protocol.instructions.md`
- `.github/instructions/code-quality.instructions.md`
- **DEC-004:** Test that models are frozen (mutation raises error)
- **DEC-005:** Test MockAdapter works without config

## ✅ Acceptance Criteria
- `pytest` passes with 80%+ coverage
- At least 15 test cases across all files
- No test depends on external API or network

## 📦 Deliverables
1. Test files (listed above)
2. Coverage report screenshot

**Points:** 5  
**Dependencies:** P1-E00 ✅  
**Owner:** Emre
