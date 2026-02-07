# AVAROS AI System - Design Plan
**Status:** DRAFT v3 - Hybrid Approach (Agents + Skills)  
**Created:** February 4, 2026  
**Last Updated:** February 4, 2026  
**Purpose:** Design AI-powered workflow for Lead Developer + Junior Developer team

---

## 📋 Table of Contents

1. [Problem Statement](#problem-statement)
2. [Architecture Overview (Hybrid Approach)](#architecture-overview)
3. [Agent Skills (Auto-Loaded Knowledge)](#agent-skills)
4. [Custom Agents (Stateful Workflow)](#custom-agents)
5. [AVAROS Development Protocols](#avaros-protocols)
6. [State Management (Context Window Solution)](#state-management)
7. [Next Steps Protocol](#next-steps-protocol)
8. [Workflow Examples](#workflow-examples)
9. [File Structure](#file-structure)
10. [Implementation Checklist](#implementation-checklist)

---

## 1. Problem Statement

### Your Role (Lead Developer)
- **Owns:** Domain layer, adapter interface, adapter implementations, QueryDispatcher, security/audit
- **Needs:** Agents to execute YOUR coding tasks with expert-level quality
- **Challenge:** Context window limitation - agents forget state between sessions

### Emre's Role (Junior Developer)
- **Works independently** using standard Copilot
- **Submits PRs** for your review
- **No dedicated agent** - you review his work

### Core Requirements
1. **Full TODO Generation** - A→Z from `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`
2. **Task Assignment** - Lead tasks vs Emre tasks (larger 1-2 day chunks)
3. **Execution** - Agents that code YOUR tasks with senior-engineer quality
4. **Quality Review** - Expert review of ALL agent work (not just Emre's PRs)
5. **PR Review** - Teaching-mode feedback for Emre's submissions
6. **Git Control** - YOU decide all merge actions (agents recommend, never auto-execute)
7. **State Persistence** - Files that survive context window resets + auto-archival
8. **Guided Workflow** - Agents recommend next steps, YOU invoke

---

## 2. Agent Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           YOU (Lead Developer)                               │
│                                                                              │
│   "Create TODO from architecture"     →  @planner                           │
│   "Do my next task"                   →  @lead-dev                          │
│   "Review the code quality"           →  @quality     ← NEW                 │
│   "Review Emre's PR #5"               →  @pr-review                         │
│   "What's the project status?"        →  @planner                           │
│                                                                              │
│   ⚠️ YOU invoke agents manually. Agents recommend next steps, YOU decide.   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER (5 Agents)                               │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │
│  │  @planner    │  │  @lead-dev   │  │  @quality    │                       │
│  │              │  │              │  │              │                       │
│  │ • Parse arch │  │ • Code domain│  │ • Review ALL │                       │
│  │ • Create TODO│  │ • Code adapt │  │   agent work │                       │
│  │ • Assign     │  │ • Code orch  │  │ • SOLID/DRY  │                       │
│  │ • Track prog │  │ • Write tests│  │ • Clean code │                       │
│  └──────────────┘  └──────────────┘  └──────────────┘                       │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐                                         │
│  │  @pr-review  │  │  @git        │                                         │
│  │              │  │              │                                         │
│  │ • Review     │  │ • Branch mgmt│                                         │
│  │   Emre's PRs │  │ • Merge (you │                                         │
│  │ • Teach mode │  │   approve)   │                                         │
│  │ • DEC checks │  │ • Conflicts  │                                         │
│  └──────────────┘  └──────────────┘                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STATE FILES (Persistent Memory)                           │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │    TODO.md       │  │   DECISIONS.md   │  │  archives/       │          │
│  │                  │  │                  │  │                  │          │
│  │ • Active tasks   │  │ • Active context │  │ • Completed TODOs│          │
│  │ • Lead vs Emre   │  │ • Recent actions │  │ • Old decisions  │          │
│  │ • Dependencies   │  │ • Handoff notes  │  │ • History        │          │
│  │ (Auto-archive    │  │ (Auto-archive    │  │                  │          │
│  │  when done)      │  │  when stale)     │  │                  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Agent Specifications

### Agent 1: @planner (Task Planner)

**Purpose:** Create and maintain the master TODO, assign tasks, track progress

**You Say:**
- "Create TODO from architecture"
- "What's the next task for me/Emre?"
- "Update project status"
- "What's blocking?"

**Capabilities:**
1. **Parse Architecture Doc** - Read `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md` and extract all implementation tasks
2. **Create TODO.md** - Generate full A→Z task list with:
   - Task ID (P1-L01, P1-E01...)
   - Description (1-2 day scope)
   - Owner (Lead / Emre)
   - Dependencies
   - Status (⬜ TODO / 🔄 IN PROGRESS / ✅ DONE / ⚠️ BLOCKED)
   - Acceptance criteria
3. **Assign Tasks** - Apply 30/70 rule (Lead gets domain/adapters/orchestration, Emre gets UI/intents/tests)
4. **Track Progress** - Update TODO.md as tasks complete
5. **Archive Completed** - Move done tasks to `docs/archives/TODO-completed.md`

**Reads:** `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`, `TODO.md`
**Writes:** `TODO.md`, `DECISIONS.md`

---

### Agent 2: @lead-dev (Lead Developer Agent)

**Purpose:** Execute YOUR coding tasks with senior-engineer quality

**You Say:**
- "Do my next task"
- "Implement [specific task ID]"
- "Fix the adapter interface"

**Capabilities:**
1. **Read Task** - Get next Lead task from TODO.md
2. **Code Implementation** - Write production-grade code for:
   - Domain models (`skill/domain/`)
   - Adapter interface and implementations (`skill/adapters/`)
   - QueryDispatcher orchestration (`skill/use_cases/`)
   - Security/audit (`skill/services/audit.py`)
3. **Follow Protocols** - Adhere to AVAROS Development Protocols (see Section 4)
4. **Write Tests** - Create tests for implemented code
5. **Update State** - Mark task progress in TODO.md, log decisions in DECISIONS.md

**Reads:** `TODO.md`, `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`, `DECISIONS.md`
**Writes:** Code files, `TODO.md`, `DECISIONS.md`

**Boundaries:**
- ✅ CAN modify: `skill/domain/`, `skill/adapters/`, `skill/use_cases/`, `skill/services/`
- ❌ CANNOT modify: `skill/web/`, `skill/locale/` (Emre's territory)

---

### Agent 3: @quality (Quality Reviewer) — NEW

**Purpose:** Review ALL agent-generated code as a Super Expert group of Software Engineers

**You Say:**
- "Review the code" (after @lead-dev finishes)
- "Quality check on [file/feature]"
- "Is this code production-ready?"

**Capabilities:**
1. **Expert-Level Code Review** - Evaluate as if 5 senior engineers reviewing:
   - **Architecture:** Clean Architecture compliance, separation of concerns
   - **SOLID:** Single responsibility, Open/closed, Liskov, Interface segregation, Dependency inversion
   - **DRY:** No code duplication, extract common patterns
   - **Clean Code:** Readable, meaningful names, small functions, no magic numbers
   - **Performance:** Efficient algorithms, proper async usage, caching where needed
   - **Error Handling:** Graceful degradation, proper exception hierarchy
   - **Type Safety:** Complete type hints, no `Any` without justification
   - **Testability:** Code is testable, dependencies injectable
   - **Security:** No hardcoded secrets, input validation, GDPR compliance

2. **Identify Issues** - Categorize findings:
   - 🔴 **CRITICAL:** Must fix before merge (architecture violations, security)
   - 🟡 **IMPORTANT:** Should fix (SOLID violations, poor naming)
   - 🔵 **SUGGESTION:** Could improve (minor optimizations)

3. **Recommend Actions** - Explain each issue with:
   - What's wrong
   - Why it matters
   - How to fix it
   - Code example if helpful

4. **Verdict:** APPROVED / NEEDS_FIXES
   - APPROVED → Ready for commit
   - NEEDS_FIXES → Back to @lead-dev with specific fixes

**Reads:** Changed files, `TODO.md`, `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`, AVAROS Protocols
**Writes:** `DECISIONS.md` (review notes)

---

### Agent 4: @pr-review (PR Reviewer for Emre)

**Purpose:** Review Emre's PRs with teaching-mode feedback

**You Say:**
- "Review Emre's PR"
- "Review PR #5"
- "Check Emre's latest code"

**Capabilities:**
1. **Fetch PR** - Get PR diff from git
2. **Architecture Check** - Verify DEC compliance:
   - Did Emre touch forbidden files? (domain/, adapters/base.py)
   - Did Emre call adapters directly instead of QueryDispatcher?
   - Did Emre hardcode credentials?
3. **Teaching Feedback** - Generate comments that TEACH, not just criticize:
   ```
   🔴 BLOCKING: [Issue]
   Why: [Explain the principle being violated]
   Fix: [Specific action to take]
   Learn: [Link to docs or concept]

   💡 SUGGESTION: [Improvement idea]
   Current: [What Emre did]
   Better: [Your suggestion with example]
   Why: [Help Emre understand the reasoning]

   ✅ GREAT: [Something Emre did well]
   [Specific praise to build confidence]
   ```
4. **Recommendation** - Explain to YOU the issues and recommend:
   - APPROVE (you decide to merge)
   - REQUEST_CHANGES (Emre needs to fix)
   - NEEDS_LEAD_FIX (issue is actually in Lead's code)

**YOU decide the action.** Agent never auto-merges.

**Reads:** Git diff, `TODO.md`, `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`
**Writes:** PR comments (via your approval), `DECISIONS.md`

---

### Agent 5: @git (Git Manager)

**Purpose:** Handle git operations with YOUR approval

**You Say:**
- "Create branch for task P1-L05"
- "Show me the merge status"
- "How do I resolve this conflict?"
- "Tag release v0.1.0"

**Capabilities:**
1. **Branch Management:**
   - Create feature branches: `feature/lead-{task-id}`, `feature/emre-{task-id}`
   - Create release branches: `release/v0.1.0`
2. **Merge Guidance:**
   - Explain the current git state
   - Show what will happen on merge
   - Recommend merge strategy (squash, rebase, merge commit)
   - **Execute ONLY after your explicit approval**
3. **Conflict Resolution:**
   - Detect and explain conflicts
   - Suggest resolution approach
   - Walk you through resolution steps
4. **Tagging:**
   - Recommend when to tag (phase completion)
   - Create tags after your approval

**Critical:** Agent EXPLAINS and RECOMMENDS, YOU APPROVE before any destructive action.

**Reads:** Git status, `DECISIONS.md`
**Writes:** Git operations (with your approval), `DECISIONS.md`

---

## 4. AVAROS Development Protocols

> **Purpose:** High standards that ALL agents and developers follow. Not bureaucracy — just best practices codified.

### Protocol 1: Architecture Compliance (DEC-001 to DEC-007)

Every code change MUST comply with these Design Decisions:

| DEC | Rule | Violation Example |
|-----|------|-------------------|
| DEC-001 | Platform-Agnostic Design | Hardcoding RENERYO URLs in skill handlers |
| DEC-002 | Universal Metric Framework | Using platform-specific metric names |
| DEC-003 | Clean Architecture | Domain importing from adapters |
| DEC-004 | Immutable Domain Models | Non-frozen dataclasses |
| DEC-005 | Zero-Config First Run | Requiring config file to start |
| DEC-006 | Settings Service Pattern | Hardcoded credentials |
| DEC-007 | Intelligence in Orchestration | Anomaly detection in adapter |

**Enforcement:** @quality and @pr-review check all changes against this table.

---

### Protocol 2: Code Quality Standards

**Naming:**
- Classes: `PascalCase` (e.g., `KPIResult`, `RENERYOAdapter`)
- Functions: `snake_case` (e.g., `get_kpi`, `build_response`)
- Constants: `UPPER_SNAKE` (e.g., `DEFAULT_TIMEOUT`)
- No abbreviations except well-known (API, KPI, OEE, ID)

**Functions:**
- Max 20 lines (extract helper functions)
- Single responsibility (one reason to change)
- Type hints on ALL parameters and return values
- Docstring with Args, Returns, Raises

**Files:**
- Max 300 lines (split into modules)
- One class per file (except small related classes)
- Imports: stdlib → third-party → local (with blank lines)

**Error Handling:**
- Never catch bare `except:`
- Custom exceptions inherit from `AvarosError`
- Log errors with context, then re-raise or return Result type

---

### Protocol 3: Testing Requirements

| Code Type | Test Requirement |
|-----------|------------------|
| Domain models | Unit tests (100% coverage) |
| Adapter implementations | Integration tests with mocked API |
| Use cases (QueryDispatcher) | Unit tests with mocked adapters |
| Intent handlers | Integration tests with test utterances |
| Web endpoints | API tests with test client |

**Test Naming:** `test_{function_name}_{scenario}_{expected_result}`
```python
def test_get_kpi_with_valid_metric_returns_kpi_result():
def test_get_kpi_with_unknown_metric_raises_metric_not_found():
```

---

### Protocol 4: Documentation Requirements

**Code Documentation:**
- Every public function has a docstring
- Complex logic has inline comments explaining WHY
- TODO comments include phase reference: `# TODO PHASE 3: Add DocuBoT integration`

**Architecture Documentation:**
- New design decisions → Add to `DECISIONS.md`
- Breaking changes → Update `AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`

---

### Protocol 5: Commit Standards

**Commit Message Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
**Scope:** `domain`, `adapters`, `skill`, `web`, `devops`

**Examples:**
```
feat(adapters): implement RENERYOAdapter get_kpi method

- Add authentication with SettingsService
- Map RENERYO response to KPIResult
- Handle rate limiting with exponential backoff

Closes P1-L01
```

---

## 5. State Management (Context Window Solution)

### The Problem
Agents lose memory when context window resets. Files get too large over time.

### Solution: Active State + Auto-Archive

**Principle:** Keep state files SMALL and RELEVANT. Archive everything else.

```
docs/
├── TODO.md              # ONLY active/in-progress tasks (small)
├── DECISIONS.md         # ONLY recent decisions (last 30 days)
└── archives/
    ├── TODO-phase1.md   # Completed Phase 1 tasks
    ├── TODO-phase2.md   # Completed Phase 2 tasks
    └── DECISIONS-2026-Q1.md  # Older decisions
```

### State File: `TODO.md`

**Maximum Size:** ~100 lines (1 phase of active tasks)

**Structure:**
```markdown
# AVAROS Active TODO

> Last Updated: 2026-02-04 by @planner
> Current Phase: 1 (Foundation)

## Quick Status
- Lead: 3/8 tasks done (P1-L04 in progress)
- Emre: 2/12 tasks done (waiting on P1-L04)
- Blocked: P1-E05 (needs P1-L04)

## Lead Tasks (Active)

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P1-L04 | Implement QueryDispatcher.get_kpi() | 🔄 IN PROGRESS | P1-L03 ✅ |
| P1-L05 | Add PostgreSQL to SettingsService | ⬜ TODO | None |
| P1-L06 | Implement RENERYOAdapter | ⬜ TODO | P1-L04 |

## Emre Tasks (Active)

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P1-E05 | Create FastAPI /api/v1/kpi endpoint | ⚠️ BLOCKED | P1-L04 |
| P1-E06 | Build React KPI display component | ⬜ TODO | P1-E05 |

## Recently Completed (Archive Soon)
- ✅ P1-L01: Create domain models (archived to TODO-phase1.md)
```

**Archive Rule:** When a task is ✅ DONE for >7 days, move to `archives/TODO-phaseX.md`

---

### State File: `DECISIONS.md`

**Maximum Size:** ~50 lines (last 10-15 decisions)

**Structure:**
```markdown
# AVAROS Active Decisions

> Last Updated: 2026-02-04 by @lead-dev
> Archive older decisions to: archives/DECISIONS-YYYY-QX.md

## Recent Decisions

### DEC-008: PostgreSQL over SQLite (2026-02-04)
**Context:** SettingsService needs database backend
**Decision:** Use PostgreSQL from day one
**Rationale:** Production-grade, supports concurrent connections
**Status:** ACTIVE

### DEC-009: Use aiohttp for async API calls (2026-02-03)
**Context:** Adapter implementations need HTTP client
**Decision:** Use aiohttp instead of requests
**Rationale:** Non-blocking I/O for voice assistant responsiveness
**Status:** ACTIVE

## Pending Decisions
- How to handle multi-tenant settings? (discuss in Phase 2)
```

**Archive Rule:** Decisions older than 30 days OR fully implemented → move to quarterly archive

---

### Auto-Archive Protocol

**Every agent session:**
1. Check TODO.md size (if >100 lines, archive completed tasks)
2. Check DECISIONS.md size (if >50 lines, archive old decisions)
3. Log: "Archived X items to archives/"

**Archive naming:**
- `TODO-phase1.md`, `TODO-phase2.md` (by phase)
- `DECISIONS-2026-Q1.md` (by quarter)

---

### State Recovery Protocol

**When ANY agent starts, it MUST:**
1. Read `TODO.md` - Get current tasks and status
2. Read `DECISIONS.md` - Get active architectural context
3. If needed, read specific archive file for history

**When ANY agent finishes, it MUST:**
1. Update `TODO.md` if task status changed
2. Update `DECISIONS.md` if architectural decision made
3. Check if archival needed (run archive protocol)

---

## 6. Next Steps Protocol

> **Principle:** Agents don't auto-handoff. They RECOMMEND, you DECIDE.

### Response Format (ALL Agents)

Every agent response MUST end with this block:

```
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [x] TODO.md: [what changed]
- [x] DECISIONS.md: [what changed, or "No changes"]

✅ COMPLETED: [Brief summary of what agent accomplished]

───────────────────────────────────────────────────────────────────────
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): [Action name]**
→ Agent: @[agent-name]
→ Prompt: "[exact prompt to copy-paste]"
→ Why: [reason this is recommended]

**Option B: [Alternative action]**
→ Agent: @[agent-name]
→ Prompt: "[exact prompt to copy-paste]"
→ Why: [when you'd choose this instead]

**Option C: Manual action needed**
→ [Description of what you need to do manually]
───────────────────────────────────────────────────────────────────────
```

---

### Agent-Specific Next Steps

#### After @planner completes:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Start your first task**
→ Agent: @lead-dev
→ Prompt: "Do task P1-L01"
→ Why: This is the first Lead task with no dependencies

**Option B: Assign tasks to Emre**
→ Action: Share TODO.md with Emre
→ His first task: P1-E01 (no dependencies)
```

#### After @lead-dev completes coding:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Quality review before commit**
→ Agent: @quality
→ Prompt: "Review the code I just wrote for P1-L01"
→ Why: Expert review catches issues before they compound

**Option B: Skip review, commit directly**
→ Agent: @git  
→ Prompt: "Commit P1-L01 with message 'feat(adapters): implement RENERYOAdapter'"
→ Why: Only if this is a trivial change
```

#### After @quality review:
```
⏭️ RECOMMENDED NEXT STEPS:

**If APPROVED:**
→ Agent: @git
→ Prompt: "Commit the reviewed code"
→ Why: Code passed expert review, safe to commit

**If NEEDS_FIXES:**
→ Agent: @lead-dev
→ Prompt: "Fix these issues: [list from review]"
→ Why: Address issues before committing
```

#### After @pr-review:
```
⏭️ RECOMMENDED NEXT STEPS:

**If issues found:**
→ Action: Post feedback to Emre's PR (I'll show you the comments)
→ Wait for Emre to fix, then: @pr-review "Re-review Emre's PR #5"

**If approved:**
→ Agent: @git
→ Prompt: "Show me merge options for PR #5"
→ Why: Decide how to merge (squash, rebase, merge commit)
```

#### After @git (before destructive action):
```
⏭️ RECOMMENDED NEXT STEPS:

**I'm ready to execute, but need your approval:**

Planned action: [e.g., "Merge PR #5 with squash into main"]
This will:
- Squash 3 commits into 1
- Delete feature/emre-ui branch
- Update main branch

**To approve:** Reply "yes" or "approve"
**To cancel:** Reply "no" or "cancel"
**To modify:** Tell me what you want different
```

---

## 7. Workflow Examples

### Workflow A: Initial Setup (Create TODO)

```
YOU: "@planner Create the full TODO from architecture doc"

@planner:
1. Reads AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md
2. Extracts all Phase 1, 2, 3 deliverables
3. Breaks into 1-2 day tasks (larger granularity)
4. Assigns: Domain/adapter/orchestration → Lead, UI/intents/tests → Emre
5. Creates TODO.md with active tasks only
6. Returns:
   "Created TODO.md with 25 tasks (8 Lead, 17 Emre)
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Start your first task
   → Agent: @lead-dev
   → Prompt: "Do task P1-L01: Create domain models"
   → Why: First Lead task, no dependencies"
```

### Workflow B: Lead Coding → Quality Review → Commit

```
YOU: "@lead-dev Do task P1-L01"

@lead-dev:
1. Reads TODO.md, finds P1-L01
2. Implements domain models with type hints, docstrings
3. Writes tests
4. Updates TODO.md: P1-L01 → 🔄 IN PROGRESS
5. Returns code summary + next steps:
   "Implemented domain models in skill/domain/models.py
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Quality review
   → Agent: @quality
   → Prompt: "Review P1-L01 domain models"
   → Why: Expert review before commit"

YOU: "@quality Review P1-L01 domain models"

@quality:
1. Reviews code against AVAROS Protocols
2. Checks SOLID, Clean Code, Type Safety
3. Finds one issue: Missing __hash__ for frozen dataclass used in set
4. Returns:
   "🟡 IMPORTANT: KPIResult used in set but missing explicit __hash__
    Fix: Add `unsafe_hash=True` to @dataclass decorator
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Fix the issue
   → Agent: @lead-dev
   → Prompt: "Fix: Add unsafe_hash=True to KPIResult dataclass"
   → Why: Minor fix, then ready to commit"

YOU: "@lead-dev Fix: Add unsafe_hash=True to KPIResult dataclass"

@lead-dev:
1. Makes the fix
2. Returns:
   "Fixed KPIResult dataclass
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Commit
   → Agent: @git
   → Prompt: "Commit P1-L01 with message 'feat(domain): add domain models'"
   → Why: Code reviewed and fixed"

YOU: "@git Commit P1-L01 with message 'feat(domain): add domain models'"

@git:
1. Shows: "Ready to commit 3 files to main branch"
2. Returns:
   "Planned action: git add skill/domain/models.py tests/test_domain/test_models.py
                    git commit -m 'feat(domain): add domain models'
   
   ⏭️ To approve: Reply 'yes'"

YOU: "yes"

@git:
1. Executes commit
2. Returns:
   "✅ Committed: feat(domain): add domain models [abc1234]
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A: Continue with next task
   → Agent: @lead-dev
   → Prompt: "Do task P1-L02"
   → Why: P1-L01 done, P1-L02 has no dependencies"
```

### Workflow C: Emre PR Review Cycle

```
YOU: "@pr-review Review Emre's PR #5"

@pr-review:
1. Fetches PR #5 diff
2. Checks architecture compliance
3. Finds issues:
   - Line 45: Calling adapter directly instead of QueryDispatcher
   - Good: Proper error handling
4. Returns:
   "PR #5 Review Summary:
   
   🔴 BLOCKING:
   - Line 45: Direct adapter call violates DEC-007
     Why: Intelligence logic should be in QueryDispatcher
     Fix: Import QueryDispatcher, call dispatcher.get_kpi()
   
   ✅ GREAT:
   - Error handling with try/except and logging
   
   RECOMMENDATION: REQUEST_CHANGES
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Request changes from Emre
   → Action: I'll generate PR comments for you to post
   → Then: Wait for Emre to fix, re-review with '@pr-review Re-review PR #5'
   
   Option B: Fix it yourself (if urgent)
   → Agent: @lead-dev  
   → Prompt: "Fix QueryDispatcher call in Emre's PR #5"
   → Why: Only if Emre is unavailable"

YOU: "Generate the PR comments"

@pr-review:
1. Generates teachable PR comments
2. Returns comment text for you to post

[Emre fixes, pushes]

YOU: "@pr-review Re-review PR #5"

@pr-review:
1. Fetches updated diff
2. All checks pass
3. Returns:
   "PR #5 Re-Review: ✅ APPROVED
   
   All issues fixed:
   - [x] Now uses QueryDispatcher correctly
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Merge the PR
   → Agent: @git
   → Prompt: "Show merge options for PR #5"
   → Why: Code approved, ready to merge"

YOU: "@git Show merge options for PR #5"

@git:
1. Analyzes PR
2. Returns:
   "PR #5 Merge Options:
   
   Option A: Squash and merge (Recommended)
   - Combines 4 commits into 1 clean commit
   - Keeps main history clean
   
   Option B: Merge commit
   - Preserves all 4 commits
   - Shows development history
   
   Option C: Rebase and merge
   - Replays commits on top of main
   - Linear history
   
   ⏭️ To proceed: Tell me which option (A, B, or C)"

YOU: "A - squash and merge"

@git:
1. Executes squash merge
2. Deletes feature branch
3. Updates TODO.md: P1-E05 → ✅ DONE
4. Returns:
   "✅ Merged PR #5 (squash)
   Branch feature/emre-ui deleted
   TODO.md updated: P1-E05 done
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A: Tell Emre to start next task
   → His next task: P1-E06 (now unblocked)"
```

---

## 8. File Structure

```
.github/
├── copilot-instructions.md           # Global rules (updated for team)
├── agents/
│   ├── planner.agent.md              # @planner - Task planning
│   ├── lead-dev.agent.md             # @lead-dev - Lead coding
│   ├── quality.agent.md              # @quality - Expert code review (NEW)
│   ├── pr-review.agent.md            # @pr-review - Emre PR review
│   └── git.agent.md                  # @git - Git operations
└── instructions/
    ├── avaros-protocols.instructions.md   # All 5 protocols
    ├── state-management.instructions.md   # TODO.md, DECISIONS.md rules
    └── next-steps.instructions.md         # Response format template

docs/
├── AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md  # Source of truth (read-only)
├── WASABI_2Call_AVAROS_Proposal.md             # Project proposal (read-only)
├── TODO.md                                      # Active tasks (agent-managed)
├── DECISIONS.md                                 # Recent decisions (agent-managed)
├── AGENT-SYSTEM-PLAN.md                        # This document
├── archive/                                     # Old docs (reference only)
└── archives/                                    # Completed tasks & old decisions
    ├── TODO-phase1.md
    └── DECISIONS-2026-Q1.md
```

---

## 9. Implementation Checklist

When you approve this plan, I'll create these files in order:

### Step 1: Instructions Files (Shared Knowledge)
- [ ] `.github/instructions/avaros-protocols.instructions.md` - The 5 protocols
- [ ] `.github/instructions/state-management.instructions.md` - TODO/DECISIONS rules
- [ ] `.github/instructions/next-steps.instructions.md` - Response format

### Step 2: Agent Files
- [ ] `.github/agents/planner.agent.md` - Task planner
- [ ] `.github/agents/lead-dev.agent.md` - Lead developer coding
- [ ] `.github/agents/quality.agent.md` - Expert code reviewer
- [ ] `.github/agents/pr-review.agent.md` - Emre PR reviewer
- [ ] `.github/agents/git.agent.md` - Git operations

### Step 3: State Files (Initial Setup)
- [ ] `docs/TODO.md` - Empty template ready for @planner
- [ ] `docs/DECISIONS.md` - Empty template with DEC-001 to DEC-007 reference
- [ ] `docs/archives/` - Create directory

### Step 4: Update Global Instructions
- [ ] Update `.github/copilot-instructions.md` for team workflow

### Step 5: Test the System
- [ ] Run @planner to create TODO from architecture doc
- [ ] Verify TODO.md is correctly formatted
- [ ] Run @lead-dev on one task
- [ ] Run @quality to review
- [ ] Verify next steps format works

---

## Summary of Changes from v1

| Aspect | v1 Plan | v2 Plan (This Version) |
|--------|---------|------------------------|
| Agents | 4 (@planner, @lead-dev, @reviewer, @git) | 5 (added @quality for expert review) |
| Emre Agent | Considered | **NO** - Emre uses standard Copilot |
| Auto-Handoff | Considered | **NO** - Agents recommend, you invoke |
| Response Format | Generic | **Structured Next Steps** with exact prompts |
| State Files | 3 (TODO, DECISIONS, AGENT-LOG) | **2** (TODO, DECISIONS) + archives |
| File Size | No limit | **Auto-archive** when >100/50 lines |
| Task Granularity | 2-4 hours | **1-2 days** (larger chunks) |
| Git Automation | Auto-merge option | **Never auto** - always explain & ask |
| Quality Review | Only for Emre's PRs | **ALL code** (agent + Emre) |

---

**Ready for your review. Tell me:**
1. Approve as-is → I'll start implementing
2. Change X → Tell me what to modify
3. Question about Y → I'll clarify
