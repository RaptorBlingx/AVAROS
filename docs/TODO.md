# AVAROS Active TODO

> Last Updated: 2026-02-08 by @task-planner
> Current Phase: Phase 1 — Foundation (Completion & Stabilization)
> Previous tasks archived to: `docs/archives/tasks-v1/`

## Quick Status
- Lead: All Phase 1 tasks complete (L01–L11). ONBOARDING.md written. Emre tasks need redefinition.
- Emre: Completing learning tasks (task3 → task5). First AVAROS tasks created (E01–E02), gated on L05+L06.
- Blocked: DocuBoT/PREVENTION = Phase 2+ (waiting on WASABI consortium)
- **Phase 1 remaining: Awaiting task redefinition from @task-planner**

---

## Lead Tasks

| ID | Task | Pts | Status | Deps |
|----|------|-----|--------|------|
| P1-L01 | Deploy WASABI OVOS locally | 3 | ✅ DONE | — |
| P1-L02 | Create AVAROS Docker integration | 5 | ✅ DONE | P1-L01 |
| P1-L03 | Test skill loads in OVOS | 3 | ✅ DONE | P1-L02 |
| P1-L04 | End-to-end voice test | 5 | ✅ DONE | P1-L03 |
| P1-L05 | GitHub/Forgejo repo setup for team | 3 | ✅ DONE | P1-L04 |
| P1-L06 | Write Emre onboarding doc (clone, stack, run skill) | 2 | ✅ DONE | P1-L05 |
| P1-L07 | Fix git branch mismatch (master → main) | 1 | ✅ DONE | — |
| P1-L08 | Rewrite fake tests to test real production code | 5 | ✅ DONE | — |
| P1-L09 | Wire ResponseBuilder into all intent handlers | 3 | ✅ DONE | — |
| P1-L10 | Fix DEC numbering conflict (Arch Plan vs DEVELOPMENT.md) | 1 | ✅ DONE | — |
| P1-L11 | Add real domain unit tests (models, exceptions, results) | 3 | ✅ DONE | P1-L08 |

### Lead Task Details

**P1-L06 — Write Emre onboarding doc** (2 pts)
> Create a 1-page `docs/ONBOARDING.md`: Forgejo clone URL, SSH key verification, Docker stack startup commands, how to run the skill, how to run tests, expected output. This is Emre's entry point — be explicit about every step. Emre has OVOS skill experience (weather skill) but has never run the WASABI stack.

**P1-L07 — Fix git branch mismatch** (1 pt)
> Local branch is `master`, remote default is `main`. Align to `main` before more code lands. Quick: `git branch -m master main && git push -u origin main`. Verify remote default branch in Forgejo settings.

**P1-L08 — Rewrite fake tests to test real production code** (5 pts)
> `tests/test_exceptions.py` (395 lines) and `tests/test_result_types.py` (464 lines) redefine `AVAROSError`, `KPIResult`, etc. locally instead of importing from `skill/domain/`. These tests prove nothing about the real codebase. Rewrite both files to:
> - Import from `skill.domain.exceptions` and `skill.domain.results`
> - Follow AAA pattern and naming convention `test_{function}_{scenario}_{expected}`
> - Cover construction, immutability, `to_dict()`, error codes, edge cases
> - Reference: `tests/test_domain/test_models.py` for correct test style
> - Reference: `DEVELOPMENT.md` L779–L983 for testing standards

**P1-L09 — Wire ResponseBuilder into intent handlers** (3 pts)
> `skill/services/response_builder.py` (303 lines) is complete but unused. Refactor `skill/__init__.py` handlers to use `ResponseBuilder.format_kpi_result()`, `format_comparison_result()`, etc. instead of inline `speak_dialog()` data formatting. Initialize `ResponseBuilder` in `AVAROSSkill.initialize()`. This replaces manual string formatting in 7 handlers with voice-optimized output.

**P1-L10 — Fix DEC numbering conflict** (1 pt)
> Architecture Plan (`docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`) uses DEC-002 for "Two-Layer Architecture" (line 100) and DEC-005 for "Async-First" (line 238). `DEVELOPMENT.md` uses DEC-002 for "Universal Metrics" and DEC-005 for "Zero-Config". Renumber the Architecture Plan DECs to DEC-020+ range to eliminate confusion. Update `docs/DECISIONS.md` if needed.

**P1-L11 — Add real domain unit tests** (3 pts)
> After P1-L08 rewrites fake tests, add comprehensive coverage for the remaining domain code: `skill/domain/results.py` (5 result types), additional `skill/domain/exceptions.py` scenarios, and any `skill/domain/models.py` gaps. Target: 100% domain layer coverage. Can share some results.py testing with Emre (P1-E02) — coordinate to avoid duplication.

---

## Emre Tasks

**Status:** P1-E01 and P1-E02 need redefinition by @task-planner
- **ONBOARDING complete** (docs/ONBOARDING.md) — setup only, not a task
- **P1-E01** — Needs redefinition (current spec is redundant with onboarding)
- **P1-E02** — Redundant with P1-L11 (domain tests already complete, 120/120 passing)

| ID | Task | Pts | Status | Deps | Spec |
|----|------|-----|--------|------|------|
| P1-E01 | ⚠️ NEEDS REDEFINITION (current: onboarding) | 2 | ⏸️ BLOCKED | Awaiting @task-planner | `docs/tasks/P1-E01-codebase-onboarding.md` |
| P1-E02 | ⚠️ REDUNDANT (domain tests done in P1-L11) | 3 | ⏸️ BLOCKED | Awaiting @task-planner | `docs/tasks/P1-E02-domain-results-tests.md` |

### Emre's Current Reality
- Emre is working on **pre-AVAROS learning tasks** (OVOS basics → device management skill → web UI bridge)
- First AVAROS tasks (E01–E02) are ready and waiting for Lead to finish L05+L06
- Emre has OVOS skill experience (completed weather skill) but has never run WASABI stack or AVAROS
- Full task specs with acceptance criteria in `docs/tasks/` — Lead copies these into Forgejo issues

### Emre Learning Tasks (Pre-AVAROS)

| Task | Status | Notes |
|------|--------|-------|
| task2 — OVOS weather skill | ✅ DONE | |
| task3 — Device management skill | 🔄 IN PROGRESS | |
| task5 — Web UI for OVOS | ⬜ TODO | After task3 |

---

## Phase 2+ (Blocked)

| Item | Status | Blocker |
|------|--------|---------|
| DocuBoT integration | ⏸️ BLOCKED | Need Docker image + API docs from WASABI |
| PREVENTION integration | ⏸️ BLOCKED | Need Docker image + API docs from WASABI |
| RENERYO adapter (real API) | ⏸️ BLOCKED | Need API credentials from ArtiBilim |

---

## Known Issues

- ~~`tests/test_exceptions.py` and `tests/test_result_types.py` test fake code~~ → ✅ Fixed in P1-L08
- ~~`skill/services/response_builder.py` unused~~ → ✅ Fixed in P1-L09
- ~~DEC numbering conflict~~ → ✅ Fixed in P1-L10
- ~~Git branch mismatch~~ → ✅ Fixed in P1-L07

---

## Suggested Execution Order (Lead)

Independent tasks can be parallelized. Recommended sequence:

1. **P1-L05** (in progress) → **P1-L06** — Unblock Emre ASAP
2. **P1-L07** — Quick win, do before any new branches
3. **P1-L08** — Biggest debt, unblocks L11 and E02
4. **P1-L09** + **P1-L10** — Can run in parallel
5. **P1-L11** — After L08 merges, coordinate with E02 to avoid overlap

---

## Sprint Progress (Emre's Quality Score)
- Tasks completed: 0
- Points earned: 0 / 0 attempted
- First-time approval rate: N/A
- **Goal:** 80%+ first-time approval rate