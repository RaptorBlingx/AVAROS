# AVAROS Project Status

> **Cross-session handoff.** Every agent reads this FIRST and updates it LAST.
> Keep this file under 40 lines. If it grows, something is wrong.

## State

- **Phase:** 1 (Foundation — Completion & Stabilization)
- **Sprint:** Phase 1 completion — 1 Lead task (2 pts) + 2 Emre tasks (5 pts) remaining
- **Last Agent:** @dev
- **Last Updated:** 2026-02-08

## Last Session

- **Task:** Fix ONBOARDING.md for zero-config + mark P1-L05 done
- **Action:** Rewrote ONBOARDING.md to be Docker-first (clone → docker run). Marked P1-L05 DONE. Simplified from 10 sections to 5 core sections with zero-touch quick start. Removed .github references (not in repo).
- **Files Changed:** docs/ONBOARDING.md (rewritten), docs/TODO.md
- **Result:** ✅ All Lead Phase 1 tasks complete (L01–L11). Emre unblocked for P1-E01.

## Blockers

- DocuBoT/PREVENTION Docker images: waiting on WASABI consortium (DEC-009)
- RENERYO API credentials: waiting on ArtiBilim backend team
- **Emre blocked on ALL AVAROS work** until Lead finishes P1-L05 + P1-L06

## Next Action (Recommended)

## Next Action (Recommended)

1. **Emre:** Start P1-E01 (codebase onboarding) — follow `docs/ONBOARDING.md`
2. **Lead:** Decide what to do with P1-E02 (redundant — domain tests done in P1-L11)
3. **@task-planner:** Create next batch of Emre tasks (adapter tests, use-case tests, integration tests)

## Active Context

- **TODO.md fully populated** — 6 Lead tasks (5 done, 1 in-progress) + 2 Emre tasks (gated on L05+L06)
- P1-L07 through P1-L11 completed (13 pts): git alignment, fake test rewrites, ResponseBuilder integration, DEC numbering fix, comprehensive domain tests
- Emre task specs in `docs/tasks/P1-E01-*.md` and `P1-E02-*.md` — ready for Forgejo issue creation
- Phase 1 total remaining: ~5 pts (3 in-progress L05 + 2 new L06)
- WASABI M2 deliverables (D1.1, D1.3) still need attention — non-code
