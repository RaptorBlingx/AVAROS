---
applyTo: "docs/**,**/*.md"
---
# State Management Instructions

> **Purpose:** Rules for managing TODO.md, DECISIONS.md, and archive protocol.

---

## The Problem

**Context Window Limitation:** Agents forget everything when context resets.

**File Size Growth:** TODO lists and decision logs grow indefinitely.

**Solution:** Active state files (small, relevant) + auto-archival (history preserved).

---

## File Locations

```
docs/
├── TODO.md              # ONLY active/in-progress tasks (~100 lines max)
├── DECISIONS.md         # ONLY recent decisions (~50 lines max)
├── tasks/               # Detailed task specifications
│   ├── P1-L01-domain-models.md
│   ├── P1-E05-api-endpoint.md
│   └── ...
└── archives/
    ├── old-docs/        # Archived documentation
    ├── TODO-phase1.md   # Completed Phase 1 tasks
    ├── TODO-phase2.md   # Completed Phase 2 tasks
    └── DECISIONS-2026-Q1.md  # Older decisions
```

---

## TODO.md Rules

### Maximum Size: ~100 Lines

**Keep it small:**
- Only active phase tasks
- Archive completed tasks after 7 days
- Archive blocked tasks if blocked >14 days

### Structure

```markdown
# AVAROS Active TODO

> Last Updated: 2026-02-04 by @planner
> Current Phase: 1 (Foundation)

## Quick Status
- Lead: 3/8 tasks done (P1-L04 in progress)
- Emre: 2/12 tasks done (waiting on P1-L04)
- Blocked: P1-E05 (needs P1-L04)

## Lead Tasks (Active)

| ID | Task | Points | Status | Dependencies | Spec |
|----|------|--------|--------|--------------|------|
| P1-L04 | Implement QueryDispatcher.get_kpi() | 5 | 🔄 IN PROGRESS | P1-L03 ✅ | Spec link |
| P1-L05 | Add PostgreSQL to SettingsService | 8 | ⬜ TODO | None | Spec link |

## Emre Tasks (Active)

| ID | Task | Points | Status | Dependencies | Spec |
|----|------|--------|--------|--------------|------|
| P1-E05 | Create FastAPI /api/v1/kpi endpoint | 3 | ⚠️ BLOCKED | P1-L04 | Spec link |

## Sprint Progress (Emre's Quality Score)
- Tasks completed: 2
- Points earned: 5 / 8 attempted (62% - needs improvement)
- First-time approval rate: 1/2 (50%)
- **Goal:** 80%+ first-time approval rate

## Recently Completed (Archive Soon)
- ✅ P1-L01: Create domain models (ready to archive)
- ✅ P1-L02: Implement adapter interface (ready to archive)
```

### Status Icons

| Icon | Meaning | When to Use |
|------|---------|-------------|
| ⬜ TODO | Not started | Task is ready to pick up |
| 🔄 IN PROGRESS | Currently working | You/agent is actively coding |
| ✅ DONE | Completed | Task finished, merged, deployed |
| ⚠️ BLOCKED | Waiting on dependency | Can't start until blocker resolved |

### When to Update TODO.md

| Event | Agent | Update |
|-------|-------|--------|
| Task starts | @lead-dev, @planner | Change ⬜ TODO → 🔄 IN PROGRESS |
| Task completes | @lead-dev, @git | Change 🔄 IN PROGRESS → ✅ DONE |
| Dependency unblocked | @planner | Change ⚠️ BLOCKED → ⬜ TODO |
| New phase starts | @planner | Archive old phase, add new tasks |
| Task blocked | @planner | Change 🔄 IN PROGRESS → ⚠️ BLOCKED |

---

## DECISIONS.md Rules

### Maximum Size: ~50 Lines

**Keep it small:**
- Only active decisions (affecting current work)
- Archive decisions older than 30 days
- Archive decisions fully implemented and stable

### Structure

```markdown
# AVAROS Active Decisions

> Last Updated: 2026-02-04 by @lead-dev
> Archive older decisions to: archives/DECISIONS-YYYY-QX.md

## Recent Decisions

> **Note:** Runtime decisions use sequential numbering starting from DEC-008.
> DEC-001 to DEC-007 are **architecture principles** (see dec-compliance.instructions.md).
> DEC-008+ are **implementation decisions** made during development.

### DEC-008: PostgreSQL over SQLite (2026-02-04)
**Context:** SettingsService needs database backend
**Decision:** Use PostgreSQL from day one
**Rationale:** Production-grade, supports concurrent connections, AVAROS targets enterprise
**Alternatives Considered:** SQLite (too simple), MongoDB (overkill)
**Status:** ACTIVE
**Owner:** Lead Developer

### DEC-009: Use aiohttp for async API calls (2026-02-03)
**Context:** Adapter implementations need HTTP client
**Decision:** Use aiohttp instead of requests
**Rationale:** Non-blocking I/O critical for voice assistant responsiveness
**Alternatives Considered:** requests (blocking), httpx (similar to aiohttp, chose aiohttp for maturity)
**Status:** ACTIVE
**Owner:** Lead Developer

## Pending Decisions
- How to handle multi-tenant settings? (discuss in Phase 2)
- Should we support GraphQL in addition to REST? (research needed)
```

### Decision Template

```markdown
### DEC-XXX: [Decision Title] (YYYY-MM-DD)
**Context:** [Why did this question come up?]
**Decision:** [What did we decide?]
**Rationale:** [Why this choice?]
**Alternatives Considered:** [What else did we consider?]
**Status:** ACTIVE / IMPLEMENTED / SUPERSEDED
**Owner:** [Lead Developer / Emre]
```

### When to Add a Decision

Add to DECISIONS.md when:
- ✅ Choosing between 2+ technologies (PostgreSQL vs SQLite)
- ✅ Changing architectural direction (add new layer, split module)
- ✅ Adding/removing a DEC principle
- ✅ Significant design choice affecting multiple files

Don't add for:
- ❌ Trivial choices (variable names, comment phrasing)
- ❌ Bug fixes (unless it reveals a design flaw)
- ❌ Small refactorings

### Decision Status Values

| Status | Meaning | When to Use |
|--------|---------|-------------|
| **ACTIVE** | Currently guiding development | Default for new decisions |
| **IMPLEMENTED** | Fully implemented, stable | Move to archive after 30 days |
| **SUPERSEDED** | Replaced by newer decision | Reference the new DEC-XXX |
| **REJECTED** | Considered but not chosen | Document WHY rejected |

---

## Archive Protocol

### When to Archive

**TODO.md:**
- Task ✅ DONE for >7 days
- Task ⚠️ BLOCKED for >14 days (move to "Blocked Backlog")
- Entire phase completed

**DECISIONS.md:**
- Decision age >30 days
- Decision fully implemented and stable
- Decision superseded by newer decision

### How to Archive

**Step 1: Create Archive File (if doesn't exist)**
```bash
# For TODO
touch docs/archives/TODO-phase1.md

# For DECISIONS
touch docs/archives/DECISIONS-2026-Q1.md
```

**Step 2: Move Content**

Copy the completed/old item to archive file with timestamp:
```markdown
# docs/archives/TODO-phase1.md

## Archived: 2026-02-04

### P1-L01: Create domain models ✅
- Completed: 2026-01-28
- Owner: Lead Developer
- Files: skill/domain/models.py, tests/test_domain/test_models.py
- Notes: Implemented KPIResult, TrendResult, ComparisonResult with frozen dataclasses
```

**Step 3: Remove from Active File**

Delete the line/section from TODO.md or DECISIONS.md

**Step 4: Log the Archive**

Add note to active file:
```markdown
## Recently Archived
- 2026-02-04: Moved P1-L01, P1-L02, P1-L03 to archives/TODO-phase1.md
```

### Archive Naming Convention

| File Type | Pattern | Example |
|-----------|---------|---------|
| TODO by phase | `TODO-phase{N}.md` | `TODO-phase1.md` |
| DECISIONS by quarter | `DECISIONS-YYYY-QX.md` | `DECISIONS-2026-Q1.md` |
| Old documentation | `old-docs/*.md` | `old-docs/SPRINT1-COMPLETION.md` |

---

## Agent Responsibilities

### Every Agent Session Start:

**MUST READ:**
1. `docs/TODO.md` - Get current task status
2. `docs/DECISIONS.md` - Get active architectural context

**MAY READ (if needed):**
3. `docs/archives/*` - Get historical context

### Every Agent Session End:

**MUST CHECK:**
1. Did I change task status? → Update TODO.md
2. Did I make an architectural decision? → Update DECISIONS.md
3. Are files too large? → Run archive protocol

**MUST LOG:**
```markdown
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [x] TODO.md: P1-L04 changed from ⬜ TODO → 🔄 IN PROGRESS
- [x] DECISIONS.md: Added DEC-010 about error handling strategy
- [x] Archived: 3 completed tasks moved to archives/TODO-phase1.md
```

---

## Specific Agent Rules

### @planner
**Responsibilities:**
- Create initial TODO.md from architecture doc
- Update task status based on progress
- Archive completed phases
- Generate detailed task specs in `docs/tasks/`

**Updates TODO.md when:**
- Creating new tasks
- Marking tasks as blocked
- Archiving completed phase

### @lead-dev
**Responsibilities:**
- Mark tasks IN PROGRESS when starting
- Mark tasks DONE when finishing (before commit)
- Log architectural decisions

**Updates TODO.md when:**
- Starting a task (⬜ → 🔄)
- Completing a task (🔄 → ✅)

**Updates DECISIONS.md when:**
- Making technology choice
- Changing design approach
- Adding new pattern

### @quality
**Responsibilities:**
- Verify decisions are followed
- Suggest new decisions if patterns emerge

**Updates DECISIONS.md when:**
- Reviewing code reveals need for new decision
- Existing decision needs clarification

### @pr-review
**Responsibilities:**
- Update Emre's task status after review
- Record story points earned/denied

**Updates TODO.md when:**
- PR approved → mark task ✅ DONE
- PR needs revision → keep task 🔄 IN PROGRESS

### @git
**Responsibilities:**
- Log merge events
- Archive completed tasks after merge

**Updates TODO.md when:**
- Merging PR → mark task ✅ DONE
- Creating release → archive old phase

---

## State Recovery

### If TODO.md is Lost/Corrupted

**Option 1: Restore from Git**
```bash
git show HEAD~1:docs/TODO.md > docs/TODO.md
```

**Option 2: Rebuild from Archives + Architecture Doc**
1. Check `docs/archives/TODO-phase*.md` for completed tasks
2. Read `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md` for remaining tasks
3. Invoke `@planner` to regenerate TODO.md

**Option 3: Start Fresh**
- Lose in-progress state (use only if other options fail)
- Invoke `@planner` to create new TODO.md

### If DECISIONS.md is Lost/Corrupted

**Option 1: Restore from Git**
```bash
git show HEAD~1:docs/DECISIONS.md > docs/DECISIONS.md
```

**Option 2: Rebuild from Git History**
```bash
git log --all --grep="DEC-" --oneline
# Review commit messages for decisions
```

**Option 3: Extract from Code Comments**
- Search codebase for `# DEC-XXX` comments
- Rebuild DECISIONS.md from these

---

## Quick Reference

### File Size Limits

| File | Max Size | Archive When |
|------|----------|--------------|
| TODO.md | ~100 lines | Phase complete or 7 days after done |
| DECISIONS.md | ~50 lines | 30 days old or fully implemented |

### Agent Update Rules

| Agent | Must Update | When |
|-------|-------------|------|
| @planner | TODO.md | Creating tasks, marking blocked |
| @lead-dev | TODO.md, DECISIONS.md | Starting/finishing tasks, making decisions |
| @quality | DECISIONS.md | Finding architectural issues |
| @pr-review | TODO.md | After PR review |
| @git | TODO.md | After merge |

### Archive Triggers

| Condition | Action |
|-----------|--------|
| TODO.md >100 lines | Archive ✅ DONE tasks |
| DECISIONS.md >50 lines | Archive old/implemented decisions |
| Phase complete | Archive entire phase to TODO-phaseX.md |
| Quarter ends | Archive decisions to DECISIONS-YYYY-QX.md |

---

## Examples

### Good TODO.md (Small, Active)

```markdown
# AVAROS Active TODO

> Last Updated: 2026-02-04
> Current Phase: 1 (Foundation)

## Lead Tasks

| ID | Task | Points | Status | Dependencies |
|----|------|--------|--------|--------------|
| P1-L04 | Implement QueryDispatcher | 5 | 🔄 IN PROGRESS | P1-L03 ✅ |
| P1-L05 | Add PostgreSQL to Settings | 8 | ⬜ TODO | None |

## Emre Tasks

| ID | Task | Points | Status | Dependencies |
|----|------|--------|--------|--------------|
| P1-E05 | FastAPI endpoint | 3 | ⚠️ BLOCKED | P1-L04 |
```
**Size:** ~15 lines. Perfect! ✅

### Bad TODO.md (Large, Unfocused)

```markdown
# AVAROS TODO

## Phase 1 Tasks (Done)
- P1-L01: Domain models ✅
- P1-L02: Adapter interface ✅
- ... (50 completed tasks)

## Phase 2 Tasks (Done)
- P2-L01: RENERYO adapter ✅
- ... (40 more completed tasks)

## Phase 3 Tasks (Active)
- P3-L01: DocuBoT integration 🔄
- ... (30 more tasks)

## Someday/Maybe
- Research blockchain integration
- ... (20 more wishlist items)
```
**Size:** 200+ lines. Too large! ❌
**Fix:** Archive Phase 1 & 2, remove "Someday/Maybe"

---

## Summary

**State files are agent memory.** Keep them small, relevant, and up-to-date.

**Archive is your history.** Don't lose information, just move it out of active state.

**Every agent is responsible.** Check state on start, update on end, archive when needed.
