---
applyTo: "**"
---
# AVAROS — AI-Voice-Assistant for Resource-Optimized Sustainable Manufacturing

## Project

AVAROS is an OVOS-based voice assistant for manufacturing environments. It provides conversational access to supply chain, energy, material, and carbon KPIs. Platform-agnostic design: adapters for any backend (RENERYO first, then SAP, Siemens, etc.). MockAdapter provides zero-config demo experience.

**WASABI OC2 experiment:** 12-month timeline (started ~Feb 2026). Deliverables include dual-pilot validation and WASABI White-Label Shop publication. KPI targets: ≥8% electricity/unit reduction, ≥5% material efficiency, ≥10% CO₂-eq reduction.

**Repository:** ssh://git@git.arti.ac/europe/AVAROS.git (Forgejo)

## Team

- **Lead Developer (Mohamad):** Domain layer, adapters, orchestration, security, architecture
- **Junior Developer (Emre):** Intent handlers, dialogs/locale, tests, Docker, Web UI
- Both developers use AI agents for coding. Tasks are feature-level (not micro-tasks).

## Agents

| Agent | Role |
|-------|------|
| **@architect** | Strategic alignment with WASABI, phase roadmaps, architecture decisions |
| **@task-planner** | Break roadmap into tasks for Lead + Emre (Forgejo issues) |
| **@dev** | Implement Lead's coding tasks |
| **@reviewer** | Review code from Lead + Emre. Teaching mode + story points for Emre. |
| **@ops** | Git operations, Docker, deployment. Approval gate for destructive ops. |

## Critical Rules (DEC-001 to DEC-007)

These are non-negotiable. Full details with examples in `DEVELOPMENT.md` L18–L251.

| DEC | Rule |
|-----|------|
| 001 | **Platform-Agnostic:** No platform names in handlers, domain, or use_cases |
| 002 | **Universal Metrics:** Canonical names only (energy_per_unit, not seu) |
| 003 | **Clean Architecture:** Domain NEVER imports from infrastructure layers |
| 004 | **Immutable Models:** All domain models use `frozen=True` |
| 005 | **Zero-Config:** Works without config files (MockAdapter fallback) |
| 006 | **Settings Service:** All credentials via SettingsService, never hardcoded |
| 007 | **Smart Orchestration:** Adapters only fetch data; intelligence in QueryDispatcher |

## Key Files

| File | Purpose |
|------|---------|
| `docs/PROJECT-STATUS.md` | Cross-session handoff — agents read FIRST, update LAST |
| `docs/TODO.md` | Active task tracker with status icons |
| `docs/DECISIONS.md` | Architecture decision log (DEC-XXX format) |
| `docs/PHASE-ROADMAP.md` | Current phase plan (maintained by @architect) |
| `DEVELOPMENT.md` | Canonical coding standards (1,316 lines — read sections on demand) |
| `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md` | Full architecture & design vision |
| `docs/WASABI_2Call_AVAROS_Proposal.md` | WASABI proposal — objectives, KPIs, timeline |

## DEVELOPMENT.md Section Index

Agents: read only the section you need, not the whole file.

| Section | Line Range |
|---------|-----------|
| Architecture Decisions (DEC-001–007) | L18–L251 |
| Naming Conventions | L255–L282 |
| SOLID Principles | L284–L477 |
| DRY Principle | L479–L541 |
| Function Standards | L543–L634 |
| File Standards | L636–L714 |
| Error Handling | L716–L777 |
| Testing Standards | L779–L983 |
| Git Workflow | L985–L1084 |
| AVAROS Conventions (metrics, intents, adapters) | L1086–L1230 |
| Quick Reference Checklists | L1232–L1279 |
