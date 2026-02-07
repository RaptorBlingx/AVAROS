# AVAROS AI System - Design Plan
**Status:** APPROVED v4 - Simplified (Agents + Instructions)  
**Created:** February 4, 2026  
**Last Updated:** February 4, 2026  
**Purpose:** Design AI-powered workflow for Lead Developer + Junior Developer team

---

## 📋 Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Custom Agents (Stateful Workflow)](#3-custom-agents-stateful-workflow)
4. [AVAROS Development Protocols](#4-avaros-development-protocols)
   - 4.5 [Error Handling Protocol](#45-error-handling-protocol)
   - 4.6 [Git Best Practices](#46-git-best-practices-team-workflow)
5. [State Management (Context Window Solution)](#5-state-management-context-window-solution)
6. [Next Steps Protocol](#6-next-steps-protocol)
7. [Workflow Examples](#7-workflow-examples)
8. [File Structure](#8-file-structure)
9. [Implementation Checklist](#9-implementation-checklist)

---

## 1. Problem Statement

### Your Role (Lead Developer)
- **Owns:** Domain layer, adapter interface, adapter implementations, QueryDispatcher, security/audit
- **Needs:** Agents to execute YOUR coding tasks with expert-level quality
- **Challenge:** Context window limitation - agents forget state between sessions

### Emre's Role (Junior Developer)
- **Sees his tasks** in Kanban board (Backlog → TODO → In Progress → In Review → Done)
- **Works on feature branches** (`feature/emre-P1-E05`)
- **Creates PRs** when task is complete
- **Notifies you** (Slack/message) that PR is ready for review
- **You invoke** `@pr-review` to review his work
- **After merge**, you move Kanban task: In Review → Done

### Your Workflow (Lead Developer)
- **Work on feature branches** (`feature/lead-P1-L01`) - NEVER push directly to main
- **Create PRs** for your own work
- **Invoke** `@quality` to review your code before merging
- **Protected main branch** - all changes via PR (you AND Emre)

### Emre's Workflow (Step-by-Step)
1. Emre checks Kanban → picks task from TODO column (e.g., P1-E05)
2. Emre: `git checkout -b feature/emre-P1-E05`
3. Emre codes, commits, pushes branch
4. Emre creates PR, moves Kanban: In Progress → In Review
5. Emre notifies you PR is ready
6. You: `@pr-review Review Emre's PR #X`
7. Agent reviews, you approve/request changes
8. If approved, you: `@git Merge PR #X`
9. Agent merges, you move Kanban: In Review → Done

### Your Workflow (Step-by-Step)
1. You: `@planner Create TODO` → generates all tasks in `docs/TODO.md`
2. You copy Emre's tasks (P1-E*) to Kanban board
3. You: `@lead-dev Do task P1-L01`
4. Agent codes, you create branch: `feature/lead-P1-L01`
5. You: `@quality Review my code`
6. If approved, you: `@git Create PR for P1-L01`
7. You: `@git Merge my PR` (self-merge after quality check)
8. Update Kanban or TODO.md: P1-L01 → ✅ DONE

### Task ID Format
| Pattern | Meaning | Example |
|---------|---------|----------|
| `P{phase}-L{seq}` | Lead Developer task | P1-L01, P2-L03 |
| `P{phase}-E{seq}` | Emre (Junior) task | P1-E01, P1-E05 |
| Phase 1 | Foundation | P1-xxx |
| Phase 2 | Integration | P2-xxx |
| Phase 3 | Intelligence | P3-xxx |

### Story Points (Complexity & Quality Incentive)

**Purpose:** Encourage Emre to self-review and prioritize quality over speed.

**Point Scale (Fibonacci Sequence):**
| Points | Complexity | Example Task | Typical Time |
|--------|------------|--------------|---------------|
| **0** | Trivial | Update docs, fix typo | < 1 hour |
| **1** | Very Easy | Add simple dialog, update config | 1-2 hours |
| **2** | Easy | Create basic dialog file, simple test | 2-4 hours |
| **3** | Medium | Implement intent handler, UI component | 4-8 hours |
| **5** | Hard | Complex API integration, state management | 1-2 days |
| **8** | Very Hard | Multi-step feature, async orchestration | 2-3 days |
| **13** | Epic | Full module (break into smaller tasks) | 3-5 days |

**Quality Rule: PR Revisions = ZERO Points**

```
✅ First-Time Approval: Emre earns full points
⚠️ Needs Revision: Emre earns ZERO points (even if fixed later)
```

**Why this works:**
- Encourages Emre to self-review before submitting
- Quality becomes measurable (points earned vs attempted)
- Fast but sloppy work = 0 points = wasted time
- Careful work = full points = visible progress

**Tracking:**
- Kanban board shows: `P1-E05 (3pts)` in task title
- After merge: You record "3 points earned" or "0 points (revision)"
- Weekly/monthly totals show quality trends

### Core Requirements
1. **Full TODO Generation** - A→Z from `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`
2. **Task Assignment** - Lead tasks vs Emre tasks (larger 1-2 day chunks)
3. **Execution** - Agents that code YOUR tasks with senior-engineer quality
4. **Quality Review** - Expert review of ALL agent work (not just Emre's PRs)
5. **PR Review** - Teaching-mode feedback for Emre's submissions
6. **Git Control** - YOU decide all merge actions (agents recommend, never auto-execute)
7. **State Persistence** - Files that survive context window resets + auto-archival
8. **Guided Workflow** - Agents recommend next steps, YOU invoke

### Task Tracking System

**Two-Layer Approach:**

| System | Purpose | Who Sees It |
|--------|---------|-------------|
| **`docs/TODO.md`** | Agent memory (Lead's tasks + ALL tasks for reference) | Agents, Lead |
| **Kanban Board** | Emre's task tracking (visual, easy updates) | Lead, Emre |

**Workflow:**
1. `@planner` generates full `docs/TODO.md` (all P1-L* and P1-E* tasks with story points)
2. You copy Emre's tasks (P1-E*) to Kanban board with points: "P1-E05 (3pts)"
3. Agents reference `docs/TODO.md` for context
4. Emre uses Kanban board to pick tasks and track progress
5. After PR review:
   - ✅ **APPROVED:** You record points earned in tracking system
   - ⚠️ **REVISION:** You record 0 points + reminder about quality
6. You update both systems after merges (TODO.md for agents, Kanban for Emre)

---

## 2. Architecture Overview

**Design Philosophy:** **Custom Agents** (stateful workflow) + **Instructions** (shared knowledge)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           YOU (Lead Developer)                               │
│                                                                              │
│   Invoke Agents:                                                            │
│   "@planner create TODO"                                                     │
│   "@lead-dev do task P1-L01"                                                 │
│   "@quality review my code"                                                  │
│   "@pr-review check Emre's PR"                                               │
│   "@git show merge options"                                                  │
│                                                                              │
│   ⚠️ YOU control agents. Agents recommend next steps, YOU decide.           │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CUSTOM AGENTS (5 Agents)                                │
│                                                                              │
│   • Identity & State Management                                             │
│   • Workflow Orchestration                                                  │
│   • TODO.md / DECISIONS.md                                                  │
│   • Next Steps Recommendations                                              │
│                                                                              │
│  @planner    @lead-dev    @quality    @pr-review    @git                    │
│                                                                              │
│  All agents reference shared instructions for:                              │
│  • AVAROS Development Protocols                                             │
│  • DEC Compliance Rules                                                     │
│  • Testing Standards                                                        │
│  • Code Quality Guidelines                                                  │
│  • Commit Message Format                                                    │
│  • State Management Rules                                                   │
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
│  │ (Auto-archive)   │  │ (Auto-archive)   │  │                  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Approach?

| Need | Solution |
|------|----------|
| **Shared knowledge** (DEC rules, protocols) | Instructions files |
| **Stateful workflow** ("Do my next task") | Custom Agents |
| **Identity & boundaries** (@lead-dev can't touch UI) | Custom Agents |
| **Workflow orchestration** (Next Steps recommendations) | Custom Agents |
| **Persistent memory** (TODO.md, DECISIONS.md) | Custom Agents |
| **Simplicity** (no preview features) | Instructions (standard) |
| **Easy maintenance** (one place to update) | Instructions |

---

## 3. Custom Agents (Stateful Workflow)

### Agent 1: @planner (Task Planner)

**Purpose:** Create and maintain the master TODO, assign tasks, track progress

**You Say:**
- "Create TODO from architecture"
- "What's the next task for me/Emre?"
- "Update project status"
- "What's blocking?"

**Capabilities:**
1. **Parse Architecture Doc** - Read `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md` and extract all implementation tasks
2. **Create Detailed Task Specifications** - For EACH task, generate:
   - **Objective** - What needs to be built and why
   - **Requirements** - Functional + technical checklist
   - **Acceptance Criteria** - How you'll know it's done
   - **Test Scenarios** - Minimum tests to verify functionality
   - **Deliverables** - Code files, docs, tests expected
   - **Resources** - Links to relevant docs, examples, APIs
   - **Success Criteria** - Measurable outcomes
3. **Follow Task Template** - Use format from `docs/task_Template.txt` as reference
4. **Generate TODO.md** - Summary table with:
   - Task ID (P1-L01, P1-E01...)
   - Brief description (1-line summary)
   - Owner (Lead / Emre)
   - **Story Points** (0-13 based on complexity)
   - Dependencies
   - Status (⬜ TODO / 🔄 IN PROGRESS / ✅ DONE / ⚠️ BLOCKED)
   - Link to detailed spec file: `tasks/P1-E05-api-endpoint.md`
5. **Create Task Files** - For each Emre task, generate:
   - `docs/tasks/P{phase}-E{seq}-{short-name}.md`
   - Full specification following template format
   - Clear enough for Emre to work independently
6. **Assign Complexity** - Story points based on:
   - Code complexity
   - Number of integration points
   - Testing requirements
   - Documentation needs
7. **Track Progress** - Update TODO.md as tasks complete
8. **Archive Completed** - Move done tasks to `docs/archives/TODO-completed.md`

**Uses Instructions:** `avaros-protocols.instructions.md` (task breakdown conventions)

**Reads:** `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`, `docs/TODO.md`
**Writes:** `docs/TODO.md`, `docs/DECISIONS.md`

---

### Agent 2: @lead-dev (Lead Developer Agent)

**Purpose:** Execute YOUR coding tasks with senior-engineer quality

**You Say:**
- "Do my next task"
- "Implement [specific task ID]"
- "Fix the adapter interface"

**Capabilities:**
1. **Read Task** - Get next Lead task from `docs/TODO.md`
2. **Code Implementation** - Write production-grade code for:
   - Domain models (`skill/domain/`)
   - Adapter interface and implementations (`skill/adapters/`)
   - QueryDispatcher orchestration (`skill/use_cases/`)
   - Security/audit (`skill/services/audit.py`)
3. **Follow Protocols** - Adhere to AVAROS Development Protocols (from `.github/instructions/`)
4. **Write Tests** - Create tests following testing-protocol instructions
5. **Update State** - Mark task progress in `docs/TODO.md`, log decisions in `docs/DECISIONS.md`

**Uses Instructions:** `avaros-protocols.instructions.md`, `dec-compliance.instructions.md`, `testing-protocol.instructions.md`, `code-quality.instructions.md`

**Reads:** `docs/TODO.md`, `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`, `docs/DECISIONS.md`
**Writes:** Code files, `docs/TODO.md`, `docs/DECISIONS.md`

**Boundaries:**
- ✅ CAN modify: `skill/domain/`, `skill/adapters/`, `skill/use_cases/`, `skill/services/`
- ❌ CANNOT modify: `skill/web/`, `skill/locale/` (Emre's territory)

---

### Agent 3: @quality (Quality Reviewer)

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

**Uses Instructions:** `code-quality.instructions.md` (SOLID/DRY/Clean Code), `dec-compliance.instructions.md` (architecture checks)

**Reads:** Changed files, `docs/TODO.md`, `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`
**Writes:** `docs/DECISIONS.md` (review notes)

---

### Agent 4: @pr-review (PR Reviewer for Emre)

**Purpose:** Review Emre's PRs with teaching-mode feedback

**You Say:**
- "Review Emre's PR"
- "Review PR #5"
- "Check Emre's latest code"

**Capabilities:**
1. **Fetch PR** - Get PR diff from git
2. **Architecture Check** - Verify DEC compliance using dec-compliance instructions:
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
   - **APPROVE** (you decide to merge) → Emre earns full story points
   - **REQUEST_CHANGES** (Emre needs to fix) → Emre earns ZERO points (quality incentive)
   - **NEEDS_LEAD_FIX** (issue is actually in Lead's code) → Emre earns full points
5. **Points Evaluation** - After review:
   ```
   ✅ APPROVED on first submission:
   "Emre earns [X] points for P1-E05. Great work!"
   
   ⚠️ NEEDS REVISION:
   "P1-E05 requires changes. Per quality rule: 0 points earned.
    Reminder: Self-review before PR to earn full points next time."
   ```

**YOU decide the action.** Agent never auto-merges.

**Uses Instructions:** `dec-compliance.instructions.md`, `code-quality.instructions.md`, `avaros-protocols.instructions.md`

**Reads:** Git diff, `docs/TODO.md`, `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md`
**Writes:** PR comments (via your approval), `docs/DECISIONS.md`

**Note:** After merge, YOU manually move Emre's task in Kanban: In Review → Done

---

### Agent 5: @git (Git Manager & Teacher)

**Purpose:** Handle git operations with YOUR approval + teach git best practices

**You Say:**
- "Create branch for task P1-L05"
- "Create PR for my work"
- "Show me the merge status"
- "How do I resolve this conflict?"
- "What's the best merge strategy here?"
- "Should I rebase or merge?"
- "Tag release v0.1.0"

**Capabilities:**
1. **Branch Management:**
   - Create feature branches: `feature/lead-{task-id}`, `feature/emre-{task-id}`
   - Create release branches: `release/v0.1.0`
   - **Remind you:** "Never push directly to main - always use PRs"
2. **PR Creation & Management:**
   - Create PRs for your completed work
   - Explain PR vs direct push benefits
   - Recommend PR title/description format
3. **Merge Guidance:**
   - Explain the current git state in plain language
   - Show what will happen on merge (with examples)
   - Recommend merge strategy (squash, rebase, merge commit) with WHY
   - **Teach:** When to use each strategy
   - **Execute ONLY after your explicit approval**
4. **Conflict Resolution:**
   - Detect and explain conflicts in simple terms
   - Suggest resolution approach with step-by-step guide
   - Walk you through resolution (learning mode)
5. **Protected Branch Setup:**
   - Help you configure branch protection rules
   - Explain why protected main is important
6. **Tagging:**
   - Recommend when to tag (phase completion)
   - Explain semantic versioning (v1.0.0, v1.1.0, etc.)
   - Create tags after your approval

**Critical:** Agent EXPLAINS and RECOMMENDS, YOU APPROVE before any destructive action.

**Teaching Mode:** Since you're learning team git workflow, agent will:
- Explain WHY before executing
- Suggest best practices
- Warn about anti-patterns ("Don't push to main directly")
- Provide learning resources when relevant

**Uses Instructions:** `avaros-protocols.instructions.md` (commit message format)

**Reads:** Git status, `docs/DECISIONS.md`
**Writes:** Git operations (with your approval), `docs/DECISIONS.md`

---

## 4. AVAROS Development Protocols

> **Purpose:** High standards that ALL agents and developers follow. Not bureaucracy — just best practices codified.

These protocols are implemented as Instructions files (`.github/instructions/`) and referenced by all agents.

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

### How Agents Reference Instructions

Agents reference instruction files using the `#file:` syntax in their agent definition:

```markdown
# Example: .github/agents/lead-dev.agent.md

Instructions:
- Follow #file:.github/instructions/avaros-protocols.instructions.md
- Follow #file:.github/instructions/dec-compliance.instructions.md
- Follow #file:.github/instructions/code-quality.instructions.md
- Follow #file:.github/instructions/testing-protocol.instructions.md
```

This tells VS Code Copilot to include those instruction files when the agent is invoked.

---

## 4.5. Error Handling Protocol

> **Principle:** Agents fail gracefully. YOU always have recovery options.

### When @lead-dev Produces Broken Code
```
Agent detects: Code doesn't compile / tests fail
Agent response:
  "⚠️ ISSUE: [Compilation error / Test failure]
   Error: [specific error message]
   
   ⏭️ RECOMMENDED NEXT STEPS:
   Option A: I'll fix this specific error
   Option B: You review and guide the fix"
```

### When @planner Can't Parse Architecture Doc
```
Agent detects: Missing sections, unclear requirements
Agent response:
  "⚠️ ISSUE: Cannot extract tasks from section [X]
   Reason: [ambiguous/missing/contradictory]
   
   ⏭️ RECOMMENDED NEXT STEPS:
   Option A: I'll create tasks for what I can parse, flag unclear items
   Option B: You clarify the architecture doc first"
```

### When @git Encounters Merge Conflicts
```
Agent detects: Conflicts that can't be auto-resolved
Agent response:
  "⚠️ MERGE CONFLICT in [files]
   Conflicting sections: [description]
   
   ⏭️ RECOMMENDED NEXT STEPS:
   Option A: I'll show you each conflict with resolution options
   Option B: You resolve manually, then call me to complete merge"
```

### When Context Resets Mid-Task
**Recovery:** Agent reads `docs/TODO.md` and `docs/DECISIONS.md` to restore state.
```
YOU: "@lead-dev continue"

Agent:
1. Reads TODO.md → finds task marked 🔄 IN PROGRESS
2. Reads DECISIONS.md → finds any recent context
3. Responds: "Resuming P1-L04. Last known state: [from files]"
```

### When TODO.md or DECISIONS.md is Corrupted/Missing
```
Agent detects: File missing or malformed
Agent response:
  "⚠️ STATE FILE ISSUE: [TODO.md/DECISIONS.md] is [missing/corrupted]
   
   ⏭️ RECOVERY OPTIONS:
   Option A: Restore from git history (git show HEAD~1:docs/TODO.md)
   Option B: Rebuild from archives/ + architecture doc
   Option C: Start fresh (loses in-progress state)"
```

---

## 4.6. Git Best Practices (Team Workflow)

> **Principle:** Protected main branch. BOTH developers use feature branches. Everything via PR.

### Why Both Work on Branches?

| Practice | Benefit |
|----------|----------|
| **Protected main** | Prevents accidental breaking changes |
| **Feature branches** | Isolated work, easy rollback, clear history |
| **PRs for everyone** | Code review, quality gate, audit trail |
| **Lead also uses PRs** | Models best practices for junior dev |

### Branch Naming Convention

```
feature/lead-P1-L01-domain-models
feature/emre-P1-E05-api-endpoint
hotfix/critical-bug-in-adapter
release/v0.1.0
```

**Format:** `<type>/<owner>-<task-id>-<short-description>`

### Workflow Comparison

#### ❌ WRONG (Old Solo-Dev Habit)
```bash
# DON'T DO THIS
git add .
git commit -m "fixed stuff"
git push origin main  # ⚠️ Direct push to main - BAD!
```

#### ✅ CORRECT (Team Workflow)
```bash
# Lead's workflow
git checkout -b feature/lead-P1-L01-domain-models
# ... code, code, code ...
git add skill/domain/
git commit -m "feat(domain): add KPIResult and TrendResult models

- Implement immutable dataclasses (DEC-004)
- Add type hints and docstrings
- Write unit tests with 100% coverage

Closes P1-L01"
git push origin feature/lead-P1-L01-domain-models

# Then in GitHub/GitLab: Create PR
# Then: @quality reviews your code
# Then: @git "Merge my PR" (after approval)
```

### Merge Strategies (When to Use Each)

| Strategy | When to Use | Result |
|----------|-------------|--------|
| **Squash** | Small features, Emre's PRs | Clean history, 1 commit per feature |
| **Rebase** | Your PRs, linear history preferred | Keeps individual commits, no merge commit |
| **Merge Commit** | Large features, multiple developers | Preserves full history, shows merge point |

**@git agent will recommend** the right strategy for each situation and explain why.

### Protected Main Configuration

Ask @git to help you set up:
1. **Require PR** before merging to main
2. **Require 1 approval** (you approve Emre's PRs)
3. **Dismiss stale reviews** when code changes
4. **No force push** to main
5. **Status checks** (optional: CI/CD tests must pass)

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

> **Note:** Runtime decisions use sequential numbering starting from DEC-008.
> DEC-001 to DEC-007 are **architecture principles** defined in Protocol 1.
> DEC-008+ are **implementation decisions** made during development.

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
3. For EACH task, creates detailed specification file in docs/tasks/
4. Generates TODO.md summary table with links to task specs
5. Breaks into 1-2 day tasks with story points
6. Assigns: Domain/adapter/orchestration → Lead, UI/intents/tests → Emre
7. Returns:
   "Created TODO.md with 25 tasks (8 Lead, 17 Emre)
   Generated 25 detailed task specification files in docs/tasks/
   
   Example task for Emre:
   - P1-E05: Create FastAPI /api/v1/kpi endpoint (3 points)
   - Spec: docs/tasks/P1-E05-api-endpoint.md
   - Includes: Objective, requirements, test scenarios, success criteria
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Review generated task specs
   → Action: Check docs/tasks/ folder
   → Why: Ensure task clarity before assigning to Emre
   
   Option B: Start your first task
   → Agent: @lead-dev
   → Prompt: "Do task P1-L01: Create domain models"
   → Why: First Lead task with no dependencies"
```

### Workflow B: Lead Coding → Quality Review → Commit

```
YOU: "@lead-dev Do task P1-L01"

@lead-dev:
1. Reads TODO.md, finds P1-L01
2. References avaros-protocols, dec-compliance instructions
3. Implements domain models with type hints, docstrings
4. Uses testing-protocol instructions for test structure
5. Updates TODO.md: P1-L01 → 🔄 IN PROGRESS
6. Returns code summary + next steps:
   "Implemented domain models in skill/domain/models.py
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A (Recommended): Quality review
   → Agent: @quality
   → Prompt: "Review P1-L01 domain models"
   → Why: Expert review before commit"

YOU: "@quality Review P1-L01 domain models"

@quality:
1. Reviews code against code-quality instructions
2. Checks dec-compliance instructions for DEC violations
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
1. Uses avaros-protocols instructions to format commit message
2. Shows: "Ready to commit 3 files to main branch"
3. Returns:
   "Planned action: git add skill/domain/models.py tests/test_domain/test_models.py
                    git commit -m 'feat(domain): add domain models'
   
   ⏭️ To approve: Reply 'yes'"

YOU: "yes"

@git:
1. Executes commit
2. Returns:
   "✅ Committed: feat(domain): add domain models [abc1234]
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A: Create PR for this work
   → Agent: @git
   → Prompt: "Create PR for feature/lead-P1-L01"
   → Why: Protected main - all changes via PR (best practice)
   
   Option B: Continue with next task
   → Agent: @lead-dev
   → Prompt: "Do task P1-L02"
   → Why: P1-L01 done, P1-L02 has no dependencies"
```

### Workflow C: Complete Git Workflow (Branch → PR → Merge)

```
YOU: "@lead-dev Do task P1-L01"

@lead-dev:
1. Creates branch: `feature/lead-P1-L01-domain-models`
2. Implements domain models
3. Writes tests
4. Commits locally
5. Returns: "Code complete. Ready for quality review."

YOU: "@quality Review P1-L01"

@quality:
Reviews → "APPROVED. Code is production-ready."

YOU: "@git Create PR for P1-L01"

@git:
1. Pushes branch to remote
2. Creates PR with title: "feat(domain): Add domain models (P1-L01)"
3. Returns:
   "PR #7 created: https://github.com/yourrepo/pull/7
   
   ⏭️ RECOMMENDED NEXT STEPS:
   
   Option A: Merge your PR now
   → Prompt: "Merge PR #7"
   → Why: Code reviewed and approved
   
   Option B: Wait and merge later
   → Why: If you want to batch multiple PRs"

YOU: "Merge PR #7"

@git:
1. Checks: PR approved, no conflicts, status checks passed
2. Returns:
   "Ready to merge PR #7 with SQUASH strategy
   This will:
   - Squash 3 commits into 1
   - Merge into main
   - Delete feature/lead-P1-L01-domain-models branch
   
   ⏭️ To approve: Reply 'yes'"

YOU: "yes"

@git:
Merges PR, deletes branch, returns:
"✅ Merged PR #7 into main [def5678]

⏭️ RECOMMENDED NEXT STEPS:

Option A: Update TODO.md and Kanban
→ Mark P1-L01 as ✅ DONE
→ Update Kanban: In Progress → Done

Option B: Start next task
→ Agent: @lead-dev
→ Prompt: "Do task P1-L02""
```

---

## 8. File Structure

```
.github/
├── copilot-instructions.md           # Global rules (updated for team)
│
├── agents/                            # Custom Agents (Stateful Workflow)
│   ├── planner.agent.md              # @planner - Task planning
│   ├── lead-dev.agent.md             # @lead-dev - Lead coding
│   ├── quality.agent.md              # @quality - Expert code review
│   ├── pr-review.agent.md            # @pr-review - Emre PR review
│   └── git.agent.md                  # @git - Git operations
│
└── instructions/                      # Shared Knowledge (Referenced by all agents)
    ├── avaros-protocols.instructions.md     # The 5 AVAROS Development Protocols
    ├── dec-compliance.instructions.md       # DEC-001 to DEC-007 reference + examples
    ├── testing-protocol.instructions.md     # Testing requirements + templates
    ├── code-quality.instructions.md         # SOLID, DRY, Clean Code standards
    ├── state-management.instructions.md     # TODO.md, DECISIONS.md rules
    └── next-steps.instructions.md           # Response format template

docs/
├── AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md  # Source of truth (read-only)
├── WASABI_2Call_AVAROS_Proposal.md             # Project proposal (read-only)
├── TODO.md                                      # Active tasks summary (agent-managed)
├── DECISIONS.md                                 # Recent decisions (agent-managed)
├── AGENT-SYSTEM-PLAN.md                        # This document
├── task_Template.txt                            # Task specification template (reference)
├── tasks/                                       # Detailed task specifications
│   ├── P1-L01-domain-models.md                 # Example Lead task spec
│   ├── P1-E05-api-endpoint.md                  # Example Emre task spec
│   └── ...                                      # One .md file per task
└── archives/                                    # All archived content
    ├── old-docs/                               # Archived documentation (formerly archive/)
    ├── TODO-phase1.md                          # Completed Phase 1 tasks
    ├── TODO-phase2.md                          # Completed Phase 2 tasks
    └── DECISIONS-2026-Q1.md                    # Older decisions
```

---

## 9. Implementation Checklist

When you approve this plan, I'll create these files in order:

### Step 1: Instructions (Shared Knowledge) ✅ DONE
All instruction files go in `.github/instructions/` with `.instructions.md` extension:

- [x] `avaros-protocols.instructions.md` - The 5 AVAROS Development Protocols + commit format
- [x] `dec-compliance.instructions.md` - DEC-001 to DEC-007 reference + examples
- [x] `testing-protocol.instructions.md` - Testing requirements + pytest patterns
- [x] `code-quality.instructions.md` - SOLID, DRY, Clean Code standards
- [x] `state-management.instructions.md` - TODO.md/DECISIONS.md rules + archive protocol
- [x] `next-steps.instructions.md` - Response format template for all agents

### Step 2: Custom Agents (Stateful Workflow) ✅ DONE
All agent files go in `.github/agents/` with `.agent.md` extension:

- [x] `planner.agent.md` - @planner: Task planning, TODO generation, task specs
- [x] `lead-dev.agent.md` - @lead-dev: Lead developer coding
- [x] `quality.agent.md` - @quality: Expert code reviewer
- [x] `pr-review.agent.md` - @pr-review: Emre PR reviewer + points evaluator
- [x] `git.agent.md` - @git: Git operations with approval + teaching mode

### Step 3: State Files (Initial Setup) ✅ DONE
- [x] `docs/TODO.md` - Empty template ready for @planner
- [x] `docs/DECISIONS.md` - Template with DEC-001 to DEC-007 reference
- [x] `docs/tasks/` - Create directory for detailed task specifications
- [x] `docs/archives/` - Create directory structure
- [x] Move `docs/archive/` contents to `docs/archives/old-docs/`
- [x] Verify `docs/task_Template.txt` exists (reference for @planner)

### Step 4: Update Global Instructions ✅ DONE
- [x] Update `.github/copilot-instructions.md` for team workflow
- [x] Add agent system overview with invocation patterns
- [x] Add instruction files reference section
- [x] Add task specification workflow diagram
- [x] Fix file reference paths - use absolute paths
- [x] Verify no errors in agent/instruction files
- [x] Add "Protocols & Standards" to task specs
- [x] Document WASABI OVOS infrastructure setup

### Step 5: Test the System
- [ ] Invoke `@planner` → creates TODO from architecture doc
- [ ] Invoke `@lead-dev` → references correct instructions
- [ ] Invoke `@quality` → reviews with SOLID/DRY criteria
- [ ] Verify Next Steps format in responses

---

## Summary of Changes Across Versions

| Aspect | v1 | v2 | v3 | v4 (This Version) |
|--------|----|----|----|--------------------|
| **Core Approach** | Agents only | Agents only | Hybrid: Agents + Skills | **Agents + Instructions** |
| **Agent Count** | 4 | 5 | 5 | 5 (same) |
| **Knowledge System** | Instructions files | Instructions files | Agent Skills (auto-load) | **Instructions files** |
| **Complexity** | Medium | Medium | High (preview features) | **Low (standard)** |
| **Environment** | VS Code only | VS Code only | CLI, coding agent | **VS Code only** |
| **Auto-Loading** | No | No | YES (skills) | **No** |
| **Emre Agent** | Considered | NO | NO | NO |
| **Auto-Handoff** | Considered | NO | NO | NO |
| **Response Format** | Generic | Structured Next Steps | Structured Next Steps | Structured Next Steps |
| **State Files** | 3 files | 2 + archives | 2 + archives | 2 + archives |
| **Task Granularity** | 2-4 hours | 1-2 days | 1-2 days | 1-2 days |
| **Git Control** | Auto-merge option | Manual approval | Manual approval | Manual approval |
| **Quality Review** | Emre's PRs only | ALL code | ALL code | ALL code |

---

## Key Benefits of v4 (Simplified Approach)

1. **Simpler structure** - No preview features, standard instructions
2. **Same functionality** - All protocols, standards, and guidelines available
3. **Easy maintenance** - One instruction file to update, all agents see it
4. **Less complexity** - No learning curve for new features
5. **Proven approach** - Standard GitHub Copilot agent pattern
6. **Fast implementation** - 6 instruction files + 5 agents = done

---

**Ready to implement. Say "start" and I'll begin with Step 1 (Instructions files).**