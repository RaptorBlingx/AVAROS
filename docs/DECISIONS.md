# AVAROS Active Decisions

> Last Updated: 2026-02-08 | Archive: [archives/DECISIONS-2026-Q1.md](archives/DECISIONS-2026-Q1.md)
> Next DEC number: **DEC-016** | Keep this file under ~50 lines.

## DEC Numbering Scheme

- **DEC-001 to DEC-007:** Core architectural principles (defined in `DEVELOPMENT.md`)
- **DEC-008 to DEC-019:** Runtime/deployment decisions (tracked here)
- **DEC-020+:** Architecture Plan principles (in `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`)

## Architecture Principles (DEC-001 — DEC-007)

Defined in `DEVELOPMENT.md` §Architecture Decisions. Quick reference:

| DEC | Principle |
|-----|-----------|
| 001 | Platform-Agnostic Design |
| 002 | Universal Metric Framework |
| 003 | Clean Architecture (layer isolation) |
| 004 | Immutable Domain Models (`frozen=True`) |
| 005 | Zero-Config First Run (MockAdapter fallback) |
| 006 | Settings Service Pattern (no hardcoded creds) |
| 007 | Intelligence in Orchestration (adapters are dumb) |

## Active Runtime Decisions

| DEC | Decision | Status |
|-----|----------|--------|
| 008 | WASABI OVOS stack as base infrastructure (expires 2027-01-31) | ACTIVE |
| 009 | DocuBoT & PREVENTION are WASABI consortium components — awaiting access | PENDING |
| 010 | AVAROS as separate Docker service joining `ovos` network | ACTIVE |
| 014 | Set `self._dir` BEFORE `super().__init__()` for intent file discovery | ACTIVE |
| 015 | E2E testing via OVOS message bus (avg 579ms roundtrip) | ACTIVE |

## Completed (archived)

| DEC | Decision | Completed |
|-----|----------|-----------|
| 011 | WASABI stack deployed, all services healthy | 2026-02-05 |
| 012 | Docker integration complete (`avaros_skill` container) | 2026-02-06 |
| 013 | Skill launcher (`launch_skill.py`) with messagebus connection | 2026-02-06 |

Details in [archives/DECISIONS-2026-Q1.md](archives/DECISIONS-2026-Q1.md).

## Pending Decisions

_None currently. Agents add new decisions here as DEC-016+._
