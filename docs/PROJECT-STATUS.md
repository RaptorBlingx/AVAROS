# AVAROS Project Status

> **Cross-session handoff.** Every agent reads this FIRST and updates it LAST.
> Keep this file under 40 lines. If it grows, something is wrong.

## State

- **Phase:** 1 (Foundation — Completion & Stabilization)
- **Sprint:** Phase 1 completion — 1 Lead task (2 pts) + 2 Emre tasks (5 pts) remaining
- **Last Agent:** @dev
- **Last Updated:** 2026-02-08

## Last Session

- **Task:** Rewrite ONBOARDING.md as pure setup (not a task) + identify task backlog issues
- **Action:** Rewrote ONBOARDING.md as 8-step setup guide (clone AVAROS + WASABI OVOS with token, run both, verify, explore structure). Removed dependencies/testing sections (Docker handles it). Identified P1-E01 (redundant with onboarding) and P1-E02 (redundant with P1-L11) need redefinition.
- **Files Changed:** docs/ONBOARDING.md (complete rewrite), docs/TODO.md
- **Result:** ✅ ONBOARDING ready. ⚠️ Emre tasks blocked — awaiting @task-planner to redefine P1-E01 and P1-E02.

## Blockers

- DocuBoT/PREVENTION Docker images: waiting on WASABI consortium (DEC-009)
- RENERYO API credentials: waiting on ArtiBilim backend team
- **Emre blocked on ALL AVAROS work** until Lead finishes P1-L05 + P1-L06

## Next Action (Recommended)

## Next Action (Recommended)

1. **@task-planner:** Redefine Emre's task backlog (P1-E01, P1-E02, and next tasks)
   - ONBOARDING.md is complete (setup only, not a development task)
   - P1-E01 current spec is redundant with onboarding
   - P1-E02 is redundant (domain tests done in P1-L11: 120/120 tests passing)
   - Suggest: Adapter tests, use-case tests, or integration tests
2. **Emre:** Follow `docs/ONBOARDING.md` to set up stacks (not a task, just setup)
3. **Emre:** Wait for @task-planner to create P1-E01 and P1-E02 (or new task IDs)

## Active Context

- **TODO.md fully populated** — 6 Lead tasks (5 done, 1 in-progress) + 2 Emre tasks (gated on L05+L06)
- P1-L07 through P1-L11 completed (13 pts): git alignment, fake test rewrites, ResponseBuilder integration, DEC numbering fix, comprehensive domain tests
- Emre task specs in `docs/tasks/P1-E01-*.md` and `P1-E02-*.md` — ready for Forgejo issue creation
- Phase 1 total remaining: ~5 pts (3 in-progress L05 + 2 new L06)
- WASABI M2 deliverables (D1.1, D1.3) still need attention — non-code
