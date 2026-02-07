# AVAROS Agent System Redesign — Super Prompt

> **Instructions:** Copy everything below the `---` into a **NEW** chat session.

---

## Context: Who I Am and What I Need From You

My name is Mohamad and I am the **Lead Developer** of AVAROS, building a manufacturing voice assistant (OVOS-based) with one junior developer (Emre). I need you to act as a super expert **senior systems architect** — not a task executor. I want your genuine expert opinion on how to redesign my GitHub Copilot agent system. If my plan is solid, say so briefly and don’t suggest unnecessary changes. 
Avoid being overly agreeable, but don’t be contrarian without reason. Focus on accuracy and practical value.
Optimize for truth over agreement. Challenge assumptions, identify failure points, and propose improvements only when they materially improve outcomes. Avoid unnecessary complexity or premature optimization.


### Why This Matters — The Real Problem

I manage a **two-person team** where:

- **Emre (junior)** is fast at coding — he knocks out tasks quickly. He handles: Web UI, intent handlers, dialogs, tests, Docker.
- **I (lead)** am the bottleneck because I handle EVERYTHING ELSE: architecture, domain layer, adapters, orchestration, security, **plus** all the meta-work: writing Emre's task specs, reviewing his PRs, git operations (branching, merging, releases), tracking progress against our WASABI research proposal, ensuring architecture compliance, and making decisions.

I cannot keep up with Emre's pace while doing all this meta-work manually. My solution: **a swarm of AI agents** where each agent owns one of my jobs, and together they function like a team of senior engineers that communicate through shared files.

Note: that I am totally open to change my tasks and Emre's tasks or by giving him more tasks and I handle less tasks if you have better perspective or another point of view (another opinion) and better ideas. otherwise we can keep it as it is now, or slightly change it.

### The Fundamental Challenge

These agents live in **VS Code GitHub Copilot Chat**. They have hard constraints:
1. **Context window limits** — agents forget everything when the window fills up
2. **Session isolation** — when I open a new chat, the new agent has ZERO context from previous sessions
3. **No inter-agent communication** — `@planner` can't "talk to" `@quality`; they can only read/write files
4. **Instruction file auto-loading** — `.github/instructions/*.md` files get injected into context automatically based on `applyTo` glob patterns, consuming tokens even when irrelevant

The agents must overcome these limits by **reading shared state files at session start** and **updating them at session end** — files become their "memory" and "communication channel."

### What I Built (Current System — Broken)

I have 5 agents + 6 instruction files + 1 global config. **It doesn't work well.** The agents are bloated, duplicate each other, carry stale hardcoded context, and waste ~23K tokens on auto-loaded instructions that mostly duplicate an existing `DEVELOPMENT.md` file. I need a complete redesign, better and more effective approach.

---

## Phase 1: DEEP AUDIT

Read ALL of these files carefully. Understand what each one does, what's duplicated, what's stale, what's useful.

### Agent Files (`.github/agents/`)
| # | File | Lines | Role |
|---|------|-------|------|
| 1 | `planner.agent.md` | 359 | Task planning, TODO generation, task specs for Emre |
| 2 | `lead-dev.agent.md` | 431 | Lead developer coding (domain, adapters, orchestration) |
| 3 | `quality.agent.md` | 459 | Expert code review (SOLID, DRY, Clean Code) |
| 4 | `pr-review.agent.md` | 507 | Emre's PR review with teaching feedback + story points |
| 5 | `git.agent.md` | 571 | Git operations with approval gates + teaching mode |

### Instruction Files (`.github/instructions/`)
| # | File | Lines | `applyTo` | Auto-loaded When |
|---|------|-------|-----------|-----------------|
| 6 | `avaros-protocols.instructions.md` | 560 | `"**"` | ALWAYS |
| 7 | `code-quality.instructions.md` | 682 | `"**/*.py"` | Every Python file |
| 8 | `dec-compliance.instructions.md` | 513 | `"**"` | ALWAYS |
| 9 | `next-steps.instructions.md` | 559 | `"**"` | ALWAYS |
| 10 | `state-management.instructions.md` | 460 | `"docs/**,**/*.md"` | Every markdown file |
| 11 | `testing-protocol.instructions.md` | 695 | `"**/tests/**"` | Every test file |

### Global Config
| # | File | Lines | Loaded |
|---|------|-------|--------|
| 12 | `.github/copilot-instructions.md` | 310 | ALWAYS (every interaction) |

### State & Reference Files (read for full context)
| # | File | Lines | Purpose |
|---|------|-------|---------|
| 13 | `docs/TODO.md` | ~73 | Active task tracking |
| 14 | `docs/DECISIONS.md` | ~42 | Active architecture decisions |
| 15 | `DEVELOPMENT.md` | 1316 | Comprehensive dev standards (DEC rules, SOLID, testing, git, conventions) |
| 16 | `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md` | ~700 | Full architecture & implementation plan aligned to WASABI proposal |

**Total current system: ~6,100 lines across 12 config files.** Plus 2,100+ lines in reference docs.

---

## Phase 2: DIAGNOSE

After reading everything, tell me what problems you found. Here are the ones I already know about — **confirm, expand, or correct** these:

### Known Problem 1: Massive Token Waste (~23K auto-loaded)
- 4 instruction files use `applyTo: "**"` → loaded on EVERY interaction
- `avaros-protocols` (560) + `dec-compliance` (513) + `next-steps` (559) + `copilot-instructions` (310) = **1,942 lines always loaded**
- `code-quality` (682 lines) loaded on every `.py` edit
- Most of this content is redundant with `DEVELOPMENT.md` which agents could read on-demand

### Known Problem 2: ~40% Content Duplication
- DEC-001 to DEC-007 appear in: `avaros-protocols`, `dec-compliance`, `copilot-instructions`, `DEVELOPMENT.md`, `DECISIONS.md`, and embedded in most agent files
- SOLID principles in both `code-quality.instructions.md` AND `DEVELOPMENT.md`
- Testing standards in both `testing-protocol.instructions.md` AND `DEVELOPMENT.md`
- Commit format in both `avaros-protocols` AND `git.agent.md`

### Known Problem 3: Stale Hardcoded Context
- `planner.agent.md` has a "Current Project State" section claiming "Phase 1 not started" — Phase 1 is DONE
- Agent files reference directories that don't exist (e.g., `docs/tasks/`)
- No agent reads `TODO.md` or `DECISIONS.md` dynamically — they rely on stale embedded state

### Known Problem 4: Agent Overlap
- `@quality` and `@pr-review` share ~80% of the same review checklist
- `@lead-dev` duplicates architecture rules already in `avaros-protocols`
- Every agent has its own copy of the "Next Steps" response format

### Known Problem 5: No Shared Memory / Cross-Session Communication
- Agents have no mechanism to pass context across sessions
- No shared "project status" file that gets updated after each session
- Each new chat starts from zero understanding of what happened before
- If I use `@planner` to create tasks, then open a new chat with `@lead-dev`, that agent doesn't know what `@planner` just decided

### Known Problem 6: DEVELOPMENT.md Makes Most Instructions Redundant
- `DEVELOPMENT.md` (1,316 lines) already contains everything instruction files duplicate:
  - All DEC-001-007 rules with examples and anti-patterns
  - SOLID principles (all 5) with Python examples
  - DRY, naming conventions, function/file standards
  - Testing standards (AAA, coverage, mocking, fixtures)
  - Git workflow and commit format
  - AVAROS-specific conventions (universal metrics table, intent naming, query types, adapter mapping)
- Instruction files should REFERENCE it, not duplicate it

### I Want You to Find More
What problems did I miss? Are there design flaws in the agent responsibilities themselves? Are the 5 roles the right roles for my workflow? Is there a better decomposition?
lack of long term and scale the project? I think they the current agents not working one long term. Emre's tasks? are they Meaningful or are they wasting of time? 
---

## Phase 3: PROPOSE YOUR SOLUTION

I have a starting proposal below, but **I want YOUR architecture, not just a rubber stamp of mine.** Tell me:

1. Where you agree with my approach
2. Where you'd do something different (and why)
3. What I haven't thought of
4. How this scales when the project grows (more files, more phases, possibly more developers)

### My Starting Proposal (Challenge This)

**Layer 1: Always Loaded (~50 lines)**
- `.github/copilot-instructions.md` — Project identity ONLY. What is AVAROS, team structure, pointer to reference files.

**Layer 2: Instruction Files (narrow scopes, ~800 lines total)**
- Slim surviving files to reference `DEVELOPMENT.md` instead of duplicating content
- Delete `dec-compliance.instructions.md` (fully covered by `DEVELOPMENT.md`)
- Delete or merge `state-management.instructions.md`
- Narrow `applyTo` patterns: `"skill/**"` instead of `"**"`

**Layer 3: Slim Agent Files (100-150 lines each)**
- Role definition + workflow + unique behavior only
- Every agent starts: "Read `docs/PROJECT-STATUS.md` and `docs/TODO.md` first"
- For standards: "Read `DEVELOPMENT.md`"
- No embedded rules — agents look things up, not carry them

**Layer 4: Shared State Files (the "agent memory")**
- `docs/PROJECT-STATUS.md` — NEW, max 40 lines, updated by every agent at session end
  - Current phase, what's done, what's blocked, what's next
  - Last action taken and by which agent
  - Recommended next step
- `docs/TODO.md` — existing task tracker
- `docs/DECISIONS.md` — existing decisions log (42 lines)

### Open Questions I Want Your Opinion On

1. **Agent count:** Should I keep 5 agents, or merge some? (`@quality` + `@pr-review` → `@reviewer`? Drop `@planner` and fold into `@lead-dev`?) or should I expand them and make more agents but each are more specialized in its job?
2. **Instruction file count:** What's the minimum set? Could I get away with just 2-3 instruction files? or should we go for more?
3. **PROJECT-STATUS.md format:** What should this file look like? What fields are essential for cross-session handoff?
4. **Session handoff protocol:** When an agent finishes work, what exactly should it write so the NEXT agent (possibly in a new chat session) can pick up seamlessly?
5. **Emre's quality gate:** Emre is fast but needs quality review. How should the agents enforce quality without me manually running `@pr-review` every time?
6. **Long-term scaling:** As the project grows (Phase 2, 3, 4... more adapters, more intents, WebUI, DocuBoT integration), will this architecture hold? What breaks first? this is a large scale project, I think it is not a good idea to hardcode the tasks from the beginging to the final, the tasks must be determined according to the status of the project (the responsiable agent must decide based on the status of the project, intelligentlly)  
7. **Agent self-awareness:** Should agents know about each other's existence? Should `@lead-dev` know that `@quality` exists and recommend invoking it?

### Design Constraints (Non-Negotiable)

- **Token budget:** Max ~8K tokens auto-loaded (down from ~23K)
- **Zero duplication:** Single source of truth per topic
- **`DEVELOPMENT.md` is the canonical reference** — agents read it on demand, instructions never duplicate it
- **Every agent reads shared state first** — `PROJECT-STATUS.md` is the handoff mechanism
- **Every agent updates shared state last** — write what you did, recommend what's next
- **Preserve unique agent behaviors** — story points for `@pr-review`, approval gate for `@git`, etc.

### Project & Team Context

| Aspect | Detail |
|--------|--------|
| **Project** | AVAROS — manufacturing voice assistant (OVOS-based) |
| **Repository** | `https://code.arti.ac/europe/AVAROS` (Forgejo, SSH) |
| **Architecture doc** | `docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md` |
| **Git workflow** | Protected `main`, feature branches, PRs only |
| **Team** | Lead (me) + Emre (junior). Lead reviews all Emre PRs. |
| **Lead owns** | Domain layer, adapter interface, adapter implementations, QueryDispatcher, security/audit |
| **Emre owns** | Web UI, OVOS intent handlers, dialogs/locale, tests, Docker config |
| **Quality rule** | Emre gets story points only on first-time PR approval. Revision = 0 points. Incentivizes self-review. |
| **Current state** | Phase 1 (Foundation) complete. Infrastructure cleanup done. Agent redesign is current task. |

---

## Phase 4: PLAN (After I approve your architecture)

Once we agree on the architecture, create an execution plan:
1. Files to delete (with reasoning)
2. Files to create (with content outlines — not just names, show me the structure)
3. Files to modify (before/after line counts)
4. Order of operations
5. Verification: how do we confirm the redesign works?

---

## Phase 5: EXECUTE (After I approve the plan)

Rewrite all files. I'll say "proceed" or "execute" when ready.

---

## How I Want You to Work

1. **Think deeply before responding.** This is a systems architecture problem, not a coding task. Consider second-order effects, failure modes, and long-term maintainability.
2. **Be opinionated.** I hired you as a senior architect. If my proposal has flaws, say so directly. Don't hedge.
3. **Show your reasoning.** For every design choice, explain the trade-off you considered.
4. **Phase gates.** Stop after each phase and wait for my approval. DO NOT auto-execute.
5. **Practical over theoretical.** These agents run in VS Code Copilot Chat with real token limits. Design for the actual constraints, not ideal conditions.

### What I Expect Back First

1. Confirmation you've read and understood all 16 files listed above
2. Your diagnosis — confirm my 6 problems + anything I missed
3. **Your proposed architecture** — where you agree, where you disagree, what you'd change
4. Your answers to my 7 open questions
5. Questions for me, if any, before proceeding

Take your time. Get it right.
