# AVAROS Project Status

> **Cross-session handoff.** Every agent reads this FIRST and updates it LAST.
> Keep this file under 40 lines. If it grows, something is wrong.

## State

- **Phase:** 1 (Foundation — Completion & Stabilization)
- **Sprint:** Phase 1 completion — 1 Lead task (2 pts) + 2 Emre tasks (5 pts) remaining
- **Last Agent:** @dev
- **Last Updated:** 2026-02-08

## Last Session

- **Task:** P1-L06 — Write Emre onboarding doc
- **Action:** Created `docs/ONBOARDING.md` with 10 sections: SSH verification, clone, project structure, dependency install, running tests, Docker standalone, WASABI integration, coding standards quick ref, first task pointer, getting help.
- **Files Changed:** docs/ONBOARDING.md (new), docs/TODO.md, docs/PROJECT-STATUS.md
- **Result:** ✅ P1-L06 complete. Emre can start P1-E01 once P1-L05 (repo access) is done.

## Blockers

- DocuBoT/PREVENTION Docker images: waiting on WASABI consortium (DEC-009)
- RENERYO API credentials: waiting on ArtiBilim backend team
- **Emre blocked on ALL AVAROS work** until Lead finishes P1-L05 + P1-L06

## Next Action (Recommended)

## Next Action (Recommended)

1. **Lead manually:** Finish P1-L05 (Forgejo repo setup — SSH keys, permissions) — last Lead blocker
2. After L05: Create Forgejo issues for P1-E01 and P1-E02 so Emre can start
3. Emre: Follow `docs/ONBOARDING.md` → P1-E01 (onboarding) → P1-E02 (domain tests)

## Active Context

- **TODO.md fully populated** — 6 Lead tasks (5 done, 1 in-progress) + 2 Emre tasks (gated on L05+L06)
- P1-L07 through P1-L11 completed (13 pts): git alignment, fake test rewrites, ResponseBuilder integration, DEC numbering fix, comprehensive domain tests
- Emre task specs in `docs/tasks/P1-E01-*.md` and `P1-E02-*.md` — ready for Forgejo issue creation
- Phase 1 total remaining: ~5 pts (3 in-progress L05 + 2 new L06)
- WASABI M2 deliverables (D1.1, D1.3) still need attention — non-code
