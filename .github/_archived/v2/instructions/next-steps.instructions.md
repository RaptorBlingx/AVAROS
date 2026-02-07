---
applyTo: "**"
---
# Next Steps Protocol

> **Purpose:** Response format template for all agents. Guides user to next action WITHOUT auto-handoff.

---

## Core Principle

**Agents RECOMMEND, you DECIDE.**

- ❌ NO auto-handoff between agents
- ❌ NO executing next step automatically
- ✅ YES recommend options with reasoning
- ✅ YES provide exact prompts to copy-paste

---

## Response Format (ALL Agents)

Every agent response MUST end with this block:

```
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [x] TODO.md: [what changed, or "No changes"]
- [x] DECISIONS.md: [what changed, or "No changes"]
- [ ] Archives: [if anything archived]

✅ COMPLETED: [Brief 1-2 sentence summary of what agent accomplished]

───────────────────────────────────────────────────────────────────────
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): [Action name]**
→ Agent: @[agent-name]
→ Prompt: "[exact prompt to copy-paste]"
→ Why: [1-2 sentences explaining why this is recommended]

**Option B: [Alternative action]**
→ Agent: @[agent-name]
→ Prompt: "[exact prompt to copy-paste]"
→ Why: [when you'd choose this instead]

**Option C: [Manual action if needed]**
→ Action: [description of what user needs to do]
→ Why: [when this is needed]
───────────────────────────────────────────────────────────────────────
```

---

## Section Breakdown

### 1. State Updated

**Purpose:** Show what changed in persistent state.

**Format:**
```
📋 STATE UPDATED:
- [x] TODO.md: P1-L04 changed from ⬜ TODO → 🔄 IN PROGRESS
- [x] DECISIONS.md: Added DEC-010 about error handling strategy
- [ ] Archives: No archival needed
```

**Rules:**
- Use `[x]` for files that changed
- Use `[ ]` for files that didn't change
- Be specific: don't just say "Updated TODO.md", say WHAT changed

### 2. Completed

**Purpose:** Summarize what the agent did.

**Format:**
```
✅ COMPLETED: Implemented QueryDispatcher.get_kpi() method with DEC-007 compliance. 
Added unit tests with mocked adapter. Code ready for quality review.
```

**Rules:**
- 1-2 sentences max
- Specific accomplishment, not vague
- Mention key deliverables (code files, tests, docs)

### 3. Recommended Next Steps

**Purpose:** Guide user to next action with clear options.

**Format:**
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Quality review before commit**
→ Agent: @quality
→ Prompt: "Review P1-L04 QueryDispatcher code"
→ Why: Expert review catches issues early, saves time later

**Option B: Skip review, commit directly**
→ Agent: @git
→ Prompt: "Commit P1-L04 with message 'feat(use_cases): implement QueryDispatcher.get_kpi()'"
→ Why: Only if this is trivial change or you're confident in code quality

**Option C: Continue with next task**
→ Agent: @lead-dev
→ Prompt: "Do task P1-L05"
→ Why: If P1-L04 isn't blocking anything and you want to batch commits
```

**Rules:**
- Always provide 2-3 options
- Mark one as "Recommended" if there's a best practice
- Include exact prompt to copy-paste
- Explain WHY each option exists

---

## Agent-Specific Next Steps

### @planner

#### After Creating TODO:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Review generated task specs**
→ Action: Open docs/tasks/ folder
→ Why: Verify task specifications are clear before assigning to Emre

**Option B: Start your first task**
→ Agent: @lead-dev
→ Prompt: "Do task P1-L01"
→ Why: First Lead task with no dependencies
```

#### After Updating Status:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A: Check what's unblocked**
→ Action: Review TODO.md for newly unblocked tasks
→ Why: P1-L04 completion may have unblocked Emre's tasks

**Option B: Assign next task to Emre**
→ Action: Notify Emre that P1-E05 is now unblocked
→ Why: He's waiting on your work
```

---

### @lead-dev

#### After Implementing Code:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Quality review**
→ Agent: @quality
→ Prompt: "Review P1-L04 QueryDispatcher code"
→ Why: Expert review before commit reduces bugs and tech debt

**Option B: Run tests first**
→ Action: Run `pytest tests/test_use_cases/test_query_dispatcher.py`
→ Why: Verify tests pass before requesting review
```

#### After Fixing Issues from Review:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Request re-review**
→ Agent: @quality
→ Prompt: "Re-review P1-L04 after fixes"
→ Why: Ensure fixes address all issues

**Option B: Commit directly**
→ Agent: @git
→ Prompt: "Create PR for P1-L04"
→ Why: If fixes were minor and you're confident
```

---

### @quality

#### After APPROVED Review:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Create PR**
→ Agent: @git
→ Prompt: "Create PR for P1-L04"
→ Why: Code passed review, ready to merge

**Option B: Continue with next task**
→ Agent: @lead-dev
→ Prompt: "Do task P1-L05"
→ Why: If you want to batch multiple tasks into one PR
```

#### After NEEDS_FIXES Review:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Fix issues now**
→ Agent: @lead-dev
→ Prompt: "Fix these issues in P1-L04: [list from review]"
→ Why: Fix while context is fresh

**Option B: Fix later**
→ Action: Add issues to TODO comments in code
→ Why: If issues are non-blocking and you need to move on
```

---

### @pr-review

#### After Reviewing Emre's PR (Approved):
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Merge PR**
→ Agent: @git
→ Prompt: "Merge PR #5 with squash"
→ Why: Code approved, ready to merge

**Option B: Wait and batch**
→ Action: Approve PR but don't merge yet
→ Why: If Emre has multiple PRs ready, merge them together
```

#### After Reviewing Emre's PR (Needs Changes):
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Post feedback**
→ Action: I'll show you the comments, you post them to PR
→ Why: Emre needs clear feedback to fix issues

**Option B: Fix it yourself**
→ Agent: @lead-dev
→ Prompt: "Fix issues in Emre's PR #5"
→ Why: Only if issue is in YOUR code (adapter interface, etc.)
```

---

### @git

#### Before Destructive Actions (ALWAYS):
```
⏭️ RECOMMENDED NEXT STEPS:

**I'm ready to execute, but need your approval:**

Planned action: Merge PR #5 with squash strategy
This will:
- Squash 3 commits into 1
- Merge into main branch
- Delete feature/emre-P1-E05 branch

**To approve:** Reply "yes" or "approve"
**To cancel:** Reply "no" or "cancel"
**To modify:** Tell me what you want different
```

#### After Creating PR:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A: Merge now**
→ Prompt: "Merge PR #7"
→ Why: If code is reviewed and approved

**Option B: Wait for CI/CD**
→ Action: Wait for tests to pass in GitHub Actions
→ Why: If you have automated checks configured
```

#### After Merge:
```
⏭️ RECOMMENDED NEXT STEPS:

**Option A: Update TODO**
→ Agent: @planner
→ Prompt: "Mark P1-L04 as done and archive if needed"
→ Why: Keep state files current

**Option B: Start next task**
→ Agent: @lead-dev
→ Prompt: "Do task P1-L05"
→ Why: P1-L04 done, P1-L05 has no dependencies
```

---

## Special Cases

### When Task Fails/Errors

```
⏭️ RECOMMENDED NEXT STEPS:

⚠️ ERROR: [Description of what went wrong]

**Option A (Recommended): I'll fix this**
→ Prompt: "Fix this error: [specific error]"
→ Why: Agent can often fix implementation errors

**Option B: You debug**
→ Action: Review [file] at [line] and tell me what to do
→ Why: If error is unclear or needs architectural decision
```

### When Blocked by External Factor

```
⏭️ RECOMMENDED NEXT STEPS:

⚠️ BLOCKED: Cannot proceed because [reason]

**Option A: Resolve blocker**
→ Action: [specific action to unblock]
→ Why: Required to continue

**Option B: Work on different task**
→ Agent: @lead-dev
→ Prompt: "Do task P1-L05 instead"
→ Why: Don't wait idle, make progress elsewhere
```

### When Multiple Good Options

```
⏭️ RECOMMENDED NEXT STEPS:

**Option A: Continue current work**
→ Agent: @lead-dev
→ Prompt: "Continue with P1-L04 tests"
→ Why: Finish what you started

**Option B: Review Emre's PR**
→ Agent: @pr-review
→ Prompt: "Review PR #5"
→ Why: Unblock Emre so he can continue

**Option C: Plan next phase**
→ Agent: @planner
→ Prompt: "Create Phase 2 TODO"
→ Why: Phase 1 is mostly done, prepare for Phase 2

No wrong choice here - depends on your priorities.
```

---

## Anti-Patterns (Don't Do This)

### ❌ BAD: Auto-handoff

```
✅ COMPLETED: Finished P1-L04.

I'm now invoking @quality to review the code...
```
**Problem:** Doesn't let user decide. Maybe user wants to run tests first.

### ❌ BAD: Vague Next Steps

```
⏭️ NEXT STEPS:

You should probably review the code or something.
```
**Problem:** No specific options, no prompts, no reasoning.

### ❌ BAD: No Options

```
⏭️ NEXT STEPS:

Invoke @quality to review.
```
**Problem:** Only one option. User needs choices for flexibility.

### ❌ BAD: Missing Prompts

```
⏭️ NEXT STEPS:

Option A: Review code
Why: Good practice
```
**Problem:** User doesn't know what to say. Provide exact prompt.

---

## Templates by Agent

### @planner Template

```
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [x] TODO.md: [specific changes]
- [ ] DECISIONS.md: No changes
- [x] Created task specs: P1-L01 through P1-L08, P1-E01 through P1-E12

✅ COMPLETED: [Summary of what planner did]

───────────────────────────────────────────────────────────────────────
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): [Best next action]**
→ Agent/Action: [who or what]
→ Prompt: "[exact text]"
→ Why: [reasoning]

**Option B: [Alternative]**
→ Agent/Action: [who or what]
→ Prompt: "[exact text]"
→ Why: [reasoning]
───────────────────────────────────────────────────────────────────────
```

### @lead-dev Template

```
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [x] TODO.md: P1-L04 status changed
- [x] DECISIONS.md: Added DEC-010 (if applicable)
- [ ] Archives: No archival needed

✅ COMPLETED: [Summary of implementation]

───────────────────────────────────────────────────────────────────────
⏭️ RECOMMENDED NEXT STEPS:

**Option A (Recommended): Quality review**
→ Agent: @quality
→ Prompt: "Review P1-L04 [component name]"
→ Why: Expert review before commit

**Option B: Run tests first**
→ Action: pytest tests/test_[component]/
→ Why: Verify tests pass before review
───────────────────────────────────────────────────────────────────────
```

### @quality Template

```
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [ ] TODO.md: No changes
- [x] DECISIONS.md: Noted review outcome
- [ ] Archives: No archival needed

✅ COMPLETED: Reviewed [component] - [APPROVED/NEEDS_FIXES]

[If NEEDS_FIXES: List of issues]

───────────────────────────────────────────────────────────────────────
⏭️ RECOMMENDED NEXT STEPS:

[If APPROVED:]
**Option A (Recommended): Create PR**
→ Agent: @git
→ Prompt: "Create PR for P1-L04"
→ Why: Code passed review, ready to merge

[If NEEDS_FIXES:]
**Option A (Recommended): Fix issues**
→ Agent: @lead-dev
→ Prompt: "Fix P1-L04 issues: [brief list]"
→ Why: Fix while context fresh
───────────────────────────────────────────────────────────────────────
```

### @pr-review Template

```
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [x] TODO.md: P1-E05 reviewed
- [ ] DECISIONS.md: No changes
- [ ] Archives: No archival needed

✅ COMPLETED: Reviewed Emre's PR #5 for P1-E05

**Points:** [X points / 0 points based on review outcome]

[Review summary]

───────────────────────────────────────────────────────────────────────
⏭️ RECOMMENDED NEXT STEPS:

[If APPROVED:]
**Option A (Recommended): Merge PR**
→ Agent: @git
→ Prompt: "Merge PR #5"
→ Why: Code approved, Emre earns [X] points

[If NEEDS_REVISION:]
**Option A (Recommended): Post feedback to Emre**
→ Action: Share comments with Emre
→ Why: He needs specific guidance to fix (0 points per quality rule)
───────────────────────────────────────────────────────────────────────
```

### @git Template (Before Destructive Action)

```
───────────────────────────────────────────────────────────────────────
📋 STATE UPDATED:
- [ ] TODO.md: Will update after merge
- [ ] DECISIONS.md: No changes
- [ ] Archives: No archival needed

✅ COMPLETED: Prepared merge for PR #5

───────────────────────────────────────────────────────────────────────
⏭️ RECOMMENDED NEXT STEPS:

**I'm ready to execute, but need your approval:**

Planned action: [Specific git command]
This will:
- [Effect 1]
- [Effect 2]
- [Effect 3]

**To approve:** Reply "yes" or "approve"
**To cancel:** Reply "no" or "cancel"
**To modify:** Tell me what you want different
───────────────────────────────────────────────────────────────────────
```

---

## Summary

**Key Points:**
1. Every agent response ends with Next Steps block
2. Always provide 2-3 options with reasoning
3. Include exact prompts to copy-paste
4. Mark recommended option
5. Never auto-execute next step

**Purpose:**
- User stays in control
- Clear path forward
- No decision fatigue
- Easy to invoke next agent
