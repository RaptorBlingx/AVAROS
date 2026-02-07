# Task P1-E00: AVAROS Codebase Onboarding (REQUIRED FIRST)

## 🎯 Objective
Get familiar with the AVAROS codebase, architecture, and development workflow
before writing any code. This is NOT optional — complete it before P1-E01+.

## 📋 Requirements

### Read These (in order)
- [ ] `README.md` — Project overview, quick start, architecture
- [ ] `DEVELOPMENT.md` — **Complete development standards** (DEC principles, code quality, testing, git workflow)
- [ ] Explore code structure (see below)

### Explore the Code
- [ ] `skill/domain/models.py` — Frozen dataclasses (DEC-004)
- [ ] `skill/adapters/base.py` — Adapter interface (DEC-001)
- [ ] `skill/adapters/mock.py` — MockAdapter (DEC-005)
- [ ] `skill/use_cases/query_dispatcher.py` — Orchestration (DEC-007)
- [ ] `skill/__init__.py` — Intent handlers
- [ ] `tests/` — Existing tests

### Prove Understanding
- [ ] Run tests locally: `bash run_tests.sh`
- [ ] Explain (in a short note or standup): What does QueryDispatcher do?
- [ ] Explain: Why doesn't `skill/__init__.py` import RENERYOAdapter?

## 📐 Protocols & Standards

All development standards are in `DEVELOPMENT.md`:
- Architecture Principles (DEC-001 to DEC-007) with examples
- Code Quality Standards (SOLID, type hints, docstrings, naming)
- Testing Standards (AAA pattern, coverage targets, mocking)
- Git Workflow (commit format, branch naming, PR process)

## ✅ Acceptance Criteria
- Can run tests locally (all pass)
- Can explain DEC-001 (platform-agnostic) in own words
- Can explain Clean Architecture layers (DEC-003)
- Created first branch + pushed (even if empty commit)

## 📦 Deliverables
1. Confirmation: tests pass locally
2. Short verbal/written summary of architecture understanding
3. First git branch pushed to repo

**Points:** 2  
**Dependencies:** P1-L05 ✅ (GitHub repo must exist)  
**Owner:** Emre
