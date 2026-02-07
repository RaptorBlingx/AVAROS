# AVAROS Active TODO

> Last Updated: 2026-02-07 by Lead (manual — agent system v3 reset)
> Current Phase: Phase 1 — Foundation
> Previous tasks archived to: `docs/archives/tasks-v1/`

## Quick Status
- Lead: All Phase 1 deployment tasks done (L01–L04). L05 (repo setup) in progress.
- Emre: Completing learning tasks (task3 → task5). No AVAROS tasks assigned yet.
- Blocked: DocuBoT/PREVENTION = Phase 2+ (waiting on WASABI consortium)
- **Task queue: EMPTY — invoke `@task-planner` to create next batch**

---

## Lead Tasks

| ID | Task | Pts | Status | Deps |
|----|------|-----|--------|------|
| P1-L01 | Deploy WASABI OVOS locally | 3 | ✅ DONE | — |
| P1-L02 | Create AVAROS Docker integration | 5 | ✅ DONE | P1-L01 |
| P1-L03 | Test skill loads in OVOS | 3 | ✅ DONE | P1-L02 |
| P1-L04 | End-to-end voice test | 5 | ✅ DONE | P1-L03 |
| P1-L05 | GitHub/Forgejo repo setup for team | 3 | 🔄 IN PROGRESS | P1-L04 |

*New Lead tasks will be added by `@task-planner` after `@architect` creates the roadmap.*

---

## Emre Tasks

**No AVAROS tasks assigned.** Previous tasks (P1-E00–E03) archived — they were created by v2 agents with stale context. `@task-planner` will create fresh tasks.

### Emre's Current Reality (for @task-planner and @architect)
- Emre is working on **pre-AVAROS learning tasks** (OVOS basics → device management skill → web UI bridge)
- Emre does **NOT** have the `wasabi-ovos` stack — Lead must provide repo link/token and setup instructions
- Emre does **NOT** have the `AVAROS` repo cloned — it's on Forgejo, Emre is a member, Lead must share the clone link
- Emre has never run the AVAROS skill or OVOS stack on his machine
- **First tasks for Emre may require Lead prep work** (e.g., finalize repo access, write onboarding instructions)
- Emre uses AI agents for coding. Tasks should be feature-level, not micro-tasks.
- Emre's learning background: completed OVOS weather skill (task2), working on device management skill (task3)

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

## Known Issues (for @task-planner to consider)

- `tests/test_exceptions.py` (395 lines) and `tests/test_result_types.py` (464 lines) test fake/duplicate code — needs rewrite
- `skill/services/response_builder.py` (303 lines) is fully implemented but unused by any handler — needs wiring
- Architecture Plan has DEC numbering conflict with DEVELOPMENT.md (DEC-002, DEC-005)
- Git: local branch is `master`, remote default is `main`

---

## Sprint Progress (Emre's Quality Score)
- Tasks completed: 0
- Points earned: 0 / 0 attempted
- First-time approval rate: N/A
- **Goal:** 80%+ first-time approval rate