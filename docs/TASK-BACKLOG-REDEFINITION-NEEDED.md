# Task Backlog Redefinition Needed

> **Date:** 2026-02-08
> **From:** Lead (Mohamad) + @dev agent
> **To:** @task-planner or @architect
> **Priority:** HIGH — Emre is blocked waiting for task definitions

---

## Situation Summary

**Phase 1 Lead tasks:** ✅ ALL COMPLETE (L01–L11, 28 story points)
- All domain tests written (120/120 passing)
- ONBOARDING.md complete (setup guide, not a task)
- Repository on Forgejo, Docker working, zero-config verified

**Phase 1 Emre tasks:** ⚠️ NEED REDEFINITION
- **P1-E01:** Current spec says "onboarding" but onboarding is now a setup doc, not a task
- **P1-E02:** Asks Emre to write domain result tests, but P1-L11 already completed them all

---

## Problem Details

### Issue 1: P1-E01 is Redundant

**Current P1-E01 spec:** `docs/tasks/P1-E01-codebase-onboarding.md`
- Task asks Emre to: clone repo, run tests, verify, explore structure
- **Problem:** This is now covered by `docs/ONBOARDING.md` (setup doc, not a task)
- **No deliverable:** Spec asks for `docs/P1-E01-onboarding-notes.md` but that's not a development task

**Recommendation:** 
- Redefine P1-E01 as a REAL development task (not onboarding)
- Emre follows ONBOARDING.md as setup (not a task), then does P1-E01 as first dev work

### Issue 2: P1-E02 is Redundant

**Current P1-E02 spec:** `docs/tasks/P1-E02-domain-results-tests.md`
- Task asks Emre to write tests for `skill/domain/results.py` (KPIResult, TrendResult, etc.)
- **Problem:** P1-L11 (Lead task) already wrote ALL domain tests:
  - `tests/test_result_types.py` (720 lines) — all 5 result types
  - `tests/test_exceptions.py` (579 lines) — full exception hierarchy
  - `tests/test_domain/test_models.py` (567 lines) — all domain models
- **Result:** 120/120 tests passing, domain layer fully covered

**Recommendation:**
- Remove P1-E02 or repurpose it for a different testing layer

---

## What's NOT Tested (Opportunities for Emre)

| Layer | Component | File | Lines | Status |
|-------|-----------|------|-------|--------|
| **Adapters** | MockAdapter | `skill/adapters/mock.py` | 245 | ⬜ No tests |
| | AdapterFactory | `skill/adapters/factory.py` | 86 | ⬜ No tests |
| **Use Cases** | QueryDispatcher | `skill/use_cases/query_dispatcher.py` | 421 | ⬜ No tests |
| **Services** | SettingsService | `skill/services/settings.py` | 187 | ⬜ No tests |
| | AuditService | `skill/services/audit.py` | 206 | ⬜ No tests |
| | ResponseBuilder | `skill/services/response_builder.py` | 303 | ⬜ No tests |
| **Integration** | Intent handlers | `skill/__init__.py` | 290 | ⬜ No tests |

**Total untested code:** ~1,738 lines

---

## Suggested New Task Backlog for Emre

### Option A: Test-Focused Track (Teaching Path)

Good for junior developer learning codebase through testing:

| ID | Task | Pts | Description |
|----|------|-----|-------------|
| **P1-E01** | Write Adapter Tests | 3 | Test MockAdapter methods (get_kpi, get_trend, etc.) + AdapterFactory |
| **P1-E02** | Write QueryDispatcher Tests | 5 | Test routing logic, fallback behavior, metric validation |
| **P1-E03** | Write Service Tests | 5 | Test SettingsService, AuditService, ResponseBuilder |
| **P1-E04** | Write Integration Tests | 5 | Test intent handlers with mocked bus |

**Total:** 18 points

### Option B: Feature-Focused Track (Production Path)

Good if you want Emre shipping features quickly:

| ID | Task | Pts | Description |
|----|------|-----|-------------|
| **P1-E01** | Turkish Locale (tr-tr) | 3 | Translate intents and dialogs to Turkish |
| **P1-E02** | Web UI Prototype | 5 | Basic React UI for KPI queries (Phase 2 prep) |
| **P1-E03** | RENERYO Adapter Shell | 5 | Stub out RENERYOAdapter (no API, just structure) |
| **P1-E04** | Docker Compose Improvements | 3 | Add healthchecks, resource limits, better logging |

**Total:** 16 points

### Option C: Mixed Track (Balanced)

| ID | Task | Pts | Description |
|----|------|-----|-------------|
| **P1-E01** | Write Adapter Tests | 3 | Test MockAdapter + AdapterFactory |
| **P1-E02** | Turkish Locale | 3 | Translate to Turkish |
| **P1-E03** | Write QueryDispatcher Tests | 5 | Test orchestration logic |
| **P1-E04** | Web UI Prototype | 5 | Basic React UI |

**Total:** 16 points

---

## Immediate Action Required

**@task-planner or @architect, please:**

1. **Review this document** and the current task specs:
   - `docs/tasks/P1-E01-codebase-onboarding.md`
   - `docs/tasks/P1-E02-domain-results-tests.md`

2. **Choose a track** (A, B, C, or propose your own)

3. **Rewrite task specs** in `docs/tasks/` folder:
   - Clear objective
   - Specific acceptance criteria
   - 2-5 story points each
   - No dependencies on redundant work

4. **Update `docs/TODO.md`** with the new Emre task list

5. **Notify Lead** when tasks are ready for Emre to start

---

## Context Files to Read

- `docs/PROJECT-STATUS.md` — Current state
- `docs/TODO.md` — Task tracker (shows P1-E01/E02 blocked)
- `docs/ONBOARDING.md` — Setup guide (NOT a task)
- `docs/PHASE-ROADMAP.md` — Phase objectives
- `DEVELOPMENT.md` — Coding standards

---

## Lead's Preference (from conversation)

**Mohamad wants:**
- Real development tasks for Emre, not meta-tasks like "read the code"
- Test writing is OK if it adds value (not redundant)
- Practical deliverables (code, tests, docs, features)
- Emre should be productive, not spinning wheels

**Mohamad does NOT want:**
- Emre running existing tests (waste of time)
- Onboarding as a "task" (it's just setup)
- Duplicate work (P1-E02 domain tests already done)
