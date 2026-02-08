# AVAROS Phase Roadmap

> Maintained by **@architect**. Read by **@task-planner** to generate tasks.
> Last Updated: 2026-02-08

---

## Current Phase

**Phase 1: Foundation — Completion & Stabilization** (M1–M2, Feb–Mar 2026)

Phase 1 infrastructure is deployed and the skill runs end-to-end in OVOS. The remaining work is **technical debt cleanup, test rewrite, wiring unused services, and Emre onboarding prep**. No new features until the foundation is solid.

---

## WASABI Alignment

| Deliverable | Due | Status |
|------------|-----|--------|
| D0.1 Kick-off pack | M1 (Feb) | On track |
| D1.1 IPR Plan | M2 (Mar) | Not started — non-code deliverable |
| D1.2 Requirements & Architecture | M2 (Mar) | ✅ Architecture Plan complete, coding standards written |
| D1.3 Experiment Handbook v0.1 | M2 (Mar) | Not started — non-code deliverable |
| D2.1 Alpha package | M3 (Apr) | Foundation in place; needs test & quality pass |
| D2.2 Beta package + security checklist | M6 (Jul) | Phase 2–3 target |

**KPI Targets (end of project, M12):**
- ≥8% electricity per unit reduction
- ≥5% material efficiency improvement
- ≥10% CO₂-eq reduction vs baseline

**Current assessment:** Code foundation supports demo-quality voice queries via MockAdapter. Real KPI measurement requires RENERYO integration (Phase 2, blocked on API credentials).

---

## Phase 1 Status — What's Done vs What Remains

### Done ✅

| Component | Evidence |
|-----------|----------|
| OVOS stack deployed locally | P1-L01, DEC-011 |
| AVAROS Docker integration | P1-L02, DEC-012 |
| Skill loads and registers intents | P1-L03 |
| End-to-end voice test (579ms avg) | P1-L04, DEC-015 |
| Domain layer (models, exceptions, results) | `skill/domain/` |
| Adapter interface (`ManufacturingAdapter` ABC) | `skill/adapters/base.py` |
| MockAdapter with demo data | `skill/adapters/mock.py` |
| AdapterFactory | `skill/adapters/factory.py` |
| QueryDispatcher (orchestration) | `skill/use_cases/query_dispatcher.py` |
| ResponseBuilder (voice formatting) | `skill/services/response_builder.py` |
| AuditLogger | `skill/services/audit.py` |
| SettingsService | `skill/services/settings.py` |
| 7 intent files + 10 dialog files (en-us) | `skill/locale/en-us/` |
| Architecture decisions DEC-001–015 | `DEVELOPMENT.md`, `DECISIONS.md` |
| Coding standards (1,316 lines) | `DEVELOPMENT.md` |

### Remaining ❌ (Phase 1 Completion)

| # | Item | Owner | Pts | Why It Matters |
|---|------|-------|-----|----------------|
| 1 | **Finalize repo access for Emre** (P1-L05) | Lead | 3 | Emre cannot start ANY AVAROS work without this |
| 2 | **Write Emre onboarding doc** (clone, stack setup, run skill) | Lead | 2 | Emre has never run OVOS or AVAROS locally |
| 3 | **Rewrite fake tests** (test_exceptions.py + test_result_types.py) | Lead | 5 | 859 lines testing locally-redefined fakes, not real code — violates DEC testing standards |
| 4 | **Wire ResponseBuilder into handlers** | Lead | 3 | Fully implemented (303 lines) but unused — dead code |
| 5 | **Fix DEC numbering conflict** | Lead | 1 | Architecture Plan DEC-002/005 conflict with DEVELOPMENT.md DEC-002/005 |
| 6 | **Fix git branch mismatch** | Lead | 1 | Local=`master`, remote default=`main` |
| 7 | **Add real unit tests for domain layer** | Lead/Emre | 3 | Domain coverage target is 100%; current real coverage unknown |

**Total remaining: ~18 story points**

---

## Priority Components (Ordered) — Phase 1 Completion

1. **Repo access + onboarding doc for Emre** — CRITICAL PATH. Emre is blocked. Every day without access is a day wasted. Lead must: share Forgejo clone URL, verify SSH key access, write a 1-page "first run" guide. This unblocks ALL Emre tasks.

2. **Fix git branch mismatch** — Quick win. Align local `master` to remote `main` before more code lands. Prevents merge confusion.

3. **Rewrite fake tests to test real code** — The 859 lines in test_exceptions.py and test_result_types.py redefine domain classes locally instead of importing from `skill/domain/`. These tests prove nothing about the actual codebase. Rewrite to import real classes per coding standards.

4. **Wire ResponseBuilder into skill handlers** — ResponseBuilder is 303 lines of working code that no handler calls. Intent handlers should use it for voice-optimized formatting instead of inline string formatting.

5. **Fix DEC numbering conflict** — Architecture Plan uses DEC-002 for "Two-Layer Architecture" and DEC-005 for "Async-First". DEVELOPMENT.md uses DEC-002 for "Universal Metrics" and DEC-005 for "Zero-Config". One set must be renumbered to avoid confusion.

6. **Add real domain tests** — After fake tests are rewritten, add proper coverage for models.py, exceptions.py, results.py. Target: 100% domain coverage.

---

## Phase 2 Plan: Core Capabilities & Integration Readiness (M3–M4, Apr–May 2026)

### Goals
- Deliver **D2.1 Alpha package** (M3 deadline)
- Emre actively contributing dialog/locale/test work
- Complete Manufacturing Skill Pack intent coverage
- Begin RENERYO adapter (if API credentials arrive)
- Web UI scaffolding (FastAPI backend)

### Priority Components (Ordered)

1. **Complete Manufacturing Skill Pack intents** — Current: 7 intents. Architecture Plan specifies full coverage for energy, scrap, supplier, OEE, anomaly, what-if, trend, comparison. Add missing intents and dialogs. *Emre task: dialog files and Turkish locale.*

2. **Turkish locale (tr-tr)** — WASABI pilot is in Turkey (ArtiBilim plastics/toy site). Turkish dialog files needed for pilot deployment. *Emre task.*

3. **RENERYO adapter skeleton** — Even without API credentials, we can define the adapter class, endpoint mapping, and data transformation logic based on expected API shape. Unblocks rapid integration when credentials arrive.

4. **Web UI backend scaffolding (FastAPI)** — Settings CRUD API, health endpoint, configuration wizard backend. React frontend is Phase 3. The FastAPI backend enables programmatic configuration and is a prerequisite for the first-run wizard.

5. **Data Ingestion Service design** — Document the MQTT/OPC-UA ingestion service architecture. Implementation in Phase 3, but design decisions needed now for Alpha package.

6. **Integration tests** — Test QueryDispatcher → MockAdapter → ResponseBuilder end-to-end in code (not just via OVOS message bus). Faster CI feedback.

### Emre's Phase 2 Tasks (requires Lead prep from Phase 1)
- Clone AVAROS repo and run skill locally (onboarding doc)
- Add Turkish locale files for all existing intents
- Write dialog files for new intents
- Write unit tests for existing handlers
- Docker development setup improvements

### Phase 2 Architectural Decisions Needed

- **DEC-016:** Web UI technology choices — FastAPI backend confirmed, but React vs. simpler alternative (htmx, Jinja templates) for MVP? Full React is Phase 3+ scope.
- **DEC-017:** RENERYO adapter authentication pattern — API key vs. OAuth2? Depends on RENERYO API docs (blocked).
- **DEC-018:** Turkish locale strategy — full translation vs. English-first with Turkish overlay?

### Phase 2 Success Criteria
- [ ] Alpha package deliverable (D2.1) ready by end of M3
- [ ] ≥15 manufacturing intents with en-us dialogs
- [ ] Turkish locale for all intents
- [ ] Emre has submitted ≥3 PRs to AVAROS repo
- [ ] Domain test coverage ≥95%
- [ ] ResponseBuilder used by all intent handlers
- [ ] FastAPI settings API serving `/health` and `/api/settings`
- [ ] Zero fake/duplicate code in test files

---

## Phase 3 Outline: Intelligent Services & Pilot Prep (M5–M6, Jun–Jul 2026)

- RENERYO adapter connected to real API
- DocuBoT integration (when Docker image received from WASABI)
- PREVENTION integration (when Docker image received from WASABI)
- Web UI frontend (React or simpler MVP)
- Security checklist for D2.2 Beta package
- Pilot deployment preparation (ArtiBilim site)
- EH v0.2 delivery

---

## Risks & Blockers

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| RENERYO API credentials delayed | Cannot build real adapter; stuck on MockAdapter | HIGH | Design adapter skeleton from expected API shape; MockAdapter covers demo scenarios |
| DocuBoT/PREVENTION images delayed | Phase 3 what-if and anomaly features blocked | MEDIUM | Client interfaces defined early; mock implementations for dev/test |
| Emre onboarding delayed | 50% of team capacity wasted | HIGH | **Lead must finish repo setup (P1-L05) and onboarding doc THIS WEEK** |
| Fake tests give false confidence | Bugs ship to production | HIGH | Rewrite tests immediately — before any new features |
| DEC numbering conflict | Agent/developer confusion | LOW | Quick fix — renumber Architecture Plan DECs to DEC-020+ range |
| Web UI scope creep | Foundation work delayed for UI | MEDIUM | Phase 1 has NO Web UI. Phase 2 = backend API only. Phase 3 = frontend. |

---

## Phase Summary Timeline

| Phase | Months | Focus | Key Deliverable |
|-------|--------|-------|-----------------|
| **1** | M1–M2 (Feb–Mar) | Foundation stabilization, Emre onboarding | Clean codebase, real tests, team ready |
| **2** | M3–M4 (Apr–May) | Intent coverage, Turkish locale, RENERYO skeleton, Web UI backend | D2.1 Alpha package |
| **3** | M5–M6 (Jun–Jul) | DocuBoT, PREVENTION, RENERYO live, Web UI frontend | D2.2 Beta + security checklist |
| **4** | M7–M10 (Aug–Nov) | Dual pilots (ArtiBilim + MEXT), KPI measurement | D3.2 Validation Report |
| **5** | M11–M12 (Dec–Jan) | Packaging, Shop publication | D4.1 Shop Listing, D4.2 Final EH |
