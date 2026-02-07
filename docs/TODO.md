# AVAROS Active TODO

> Last Updated: 2026-02-06 by @lead-dev
> Current Phase: Phase 1 — Deployment & Integration

## Quick Status
- Lead: 4/5 tasks done | Next: **P1-L05**
- Emre: On learning tasks (task2→task3→task5) | Next after L05: **P1-E00**
- Blocked: DocuBoT/PREVENTION = Phase 2 (waiting on WASABI consortium)

---

## Lead Tasks (Deployment Pipeline)

| ID | Task | Pts | Status | Deps | Spec |
|----|------|-----|--------|------|------|
| P1-L01 | Deploy WASABI OVOS locally | 3 | ✅ DONE | — | [Spec](tasks/P1-L01-deploy-wasabi-ovos.md) |
| P1-L02 | Create AVAROS Docker integration | 5 | ✅ DONE | P1-L01 | [Spec](tasks/P1-L02-avaros-docker-integration.md) |
| P1-L03 | Test skill loads in OVOS | 3 | ✅ DONE | P1-L02 | [Spec](tasks/P1-L03-test-skill-loads.md) |
| P1-L04 | End-to-end voice test | 5 | ✅ DONE | P1-L03 | [Spec](tasks/P1-L04-e2e-voice-test.md) |
| P1-L05 | Create GitHub repo for team | 3 | 🔄 IN PROGRESS | P1-L04 | [Spec](tasks/P1-L05-github-repo-setup.md) |

**Lead total:** 19 points

---

## Emre Tasks (After GitHub Repo Ready)

| ID | Task | Pts | Status | Deps | Spec |
|----|------|-----|--------|------|------|
| P1-E00 | Codebase onboarding (REQUIRED) | 2 | ⬜ TODO | P1-L05 | [Spec](tasks/P1-E00-codebase-onboarding.md) |
| P1-E01 | Add unit tests (80%+ coverage) | 5 | ⬜ TODO | P1-E00 | [Spec](tasks/P1-E01-unit-tests.md) |
| P1-E02 | Turkish locale (tr-tr) | 3 | ⬜ TODO | P1-E00 | [Spec](tasks/P1-E02-turkish-locale.md) |
| P1-E03 | Docker dev environment setup | 2 | ⬜ TODO | P1-E00, P1-L02 | [Spec](tasks/P1-E03-docker-dev-setup.md) |

**Emre total:** 12 points
**Note:** Emre is currently on learning tasks (task2→task3→task5). AVAROS tasks start after P1-L05.

---

## Emre Learning Tasks (Pre-AVAROS)

| Task | Status | Notes |
|------|--------|-------|
| task2.txt — OVOS basics | ✅ DONE | |
| task3.txt — Device management skill | 🔄 IN PROGRESS | |
| task5.txt — Web UI for OVOS | ⬜ TODO | After task3 |

---

## Phase 2 (Blocked — Waiting on WASABI Consortium)

| Item | Status | Blocker |
|------|--------|---------|
| DocuBoT integration | ⏸️ BLOCKED | Need Docker image + API docs from WASABI |
| PREVENTION integration | ⏸️ BLOCKED | Need Docker image + API docs from WASABI |
| RENERYO adapter (real API) | ⏸️ BLOCKED | Need API credentials from ArtiBilim |

---

## Sprint Progress (Emre's Quality Score)
- Tasks completed: 0
- Points earned: 0 / 0 attempted
- First-time approval rate: N/A
- **Goal:** 80%+ first-time approval rate

## Recently Completed
- ✅ Sprint 1: Domain models, adapters, orchestration, tests (all done)
- ✅ DEC-008–010 documented
- ✅ P1-L01: WASABI OVOS stack deployed (all containers healthy, Hivemind client created)
- ✅ P1-L02: AVAROS Docker integration (container running, joined ovos network)
- ✅ P1-L03: Skill loads and registers intents (8 intents, 94 templates, MockAdapter initialized)
- ✅ P1-L04: E2E voice test (3 intents tested, avg roundtrip 579ms, all tests passed)
