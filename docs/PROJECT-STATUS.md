# AVAROS Project Status

> **Cross-session handoff.** Every agent reads this FIRST and updates it LAST.
> Keep this file under 40 lines. If it grows, something is wrong.

## State

- **Phase:** 1 (Foundation — Completion & Stabilization)
- **Sprint:** Phase 1 completion — 5 Lead tasks (14 pts) + 2 Emre tasks (5 pts) remaining
- **Last Agent:** @dev
- **Last Updated:** 2026-02-08

## Last Session

- **Task:** P1-L07 — Fix git branch mismatch (master → main)
- **Action:** Renamed local branch master→main, pushed to origin, deleted old origin/master. Repository now uses main as sole default branch.
- **Files Changed:** docs/TODO.md (P1-L07 → ✅ DONE), docs/PROJECT-STATUS.md (updated)
- **Result:** Git branch alignment complete. All future commits and clones will use main branch. No more master/main confusion.

## Blockers

- DocuBoT/PREVENTION Docker images: waiting on WASABI consortium (DEC-009)
- RENERYO API credentials: waiting on ArtiBilim backend team
- **Emre blocked on ALL AVAROS work** until Lead finishes P1-L05 + P1-L06

## Next Action (Recommended)

1. `@dev` — "Do P1-L08 (rewrite fake tests) — biggest debt, 5 pts"
2. `@dev` — "Do P1-L09 (wire ResponseBuilder) or P1-L10 (fix DEC numbering) — 3 pts or 1 pt"
3. Lead manually: finish P1-L05, then P1-L06 (onboarding doc) to unblock Emre

## Active Context

- **TODO.md fully populated** — 6 Lead tasks + 2 Emre tasks with execution order
- Emre task specs in `docs/tasks/P1-E01-*.md` and `P1-E02-*.md` — ready for Forgejo issue creation
- Phase 1 total remaining: ~18 pts (3 in-progress L05 + 15 new)
- WASABI M2 deliverables (D1.1, D1.3) still need attention — non-code
