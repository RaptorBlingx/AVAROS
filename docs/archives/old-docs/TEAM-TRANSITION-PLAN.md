# AVAROS Team Transition Plan
**Modified Option B: Learn Leadership on Familiar Ground**

*Created: February 4, 2026*  
*Team: You (Lead Developer) + Emre (Junior Developer)*

---

## 📋 Executive Summary

**Recommendation: Modified Option B** - Stay on AVAROS and restructure your role to balance hands-on coding with team leadership. Code the critical 30% of the system (domain, adapters, orchestration) while Emre handles the safer 70% (UI, intents, tests). Learn technical leadership on familiar ground before taking on unknown projects.

### Why Modified Option B?

| Factor | Analysis |
|--------|----------|
| **Your Strength** | Deep AVAROS knowledge (OVOS, DocuBoT, RENERYO, PREVENTION) |
| **Your Learning Gap** | Team coordination, PR reviews, task planning |
| **Emre's Strength** | Frontend, fast learner, motivated |
| **Emre's Learning Gap** | Manufacturing domain, Python backend, AVAROS architecture |
| **Risk of HEDGE Separation** | You'd manage a project you don't understand - that's not leading, it's hoping |
| **Benefit of AVAROS Division** | Practice leadership with minimal technical risk |

**Core Principle:** *Learn management on familiar technical ground, THEN expand to new domains.*

---

## 🎯 Work Division Strategy

### You Code (Critical 30%)
These are **architectural foundation** components where mistakes cascade:

#### 1. Domain Layer (`skill/domain/`)
- **Why you:** Defines universal manufacturing concepts - gets wrong, everything breaks
- **What:** `CanonicalMetric` definitions, frozen dataclasses, domain exceptions
- **Current status:** ✅ Already well-aligned (keep maintaining)
- **Emre dependency:** He builds UI/intents on top of YOUR domain models

#### 2. Adapter Interface & Implementations (`skill/adapters/`)
- **Why you:** Translates RENERYO/SAP/Siemens APIs to AVAROS concepts - requires deep understanding
- **What:** `ManufacturingAdapter` ABC, `RENERYOAdapter`, platform config mappings
- **Current status:** ⚠️ **NEEDS FIX** (see Section 3 below)
- **Emre dependency:** He uses adapters via QueryDispatcher, doesn't touch adapter internals

#### 3. Orchestration Logic (`skill/services/query_dispatcher.py`)
- **Why you:** Routes queries, integrates DocuBoT/PREVENTION, handles fallback logic
- **What:** Query routing, intelligence service orchestration, error handling
- **Current status:** ⚠️ Phase 1 basic, needs Phase 3 DocuBoT/PREVENTION integration
- **Emre dependency:** He calls dispatcher from intent handlers, doesn't modify routing

#### 4. Security & Compliance (`skill/services/audit.py`)
- **Why you:** GDPR, AI Act, ISO 27001 compliance - legal consequences if wrong
- **What:** Immutable audit logs, RBAC enforcement, data retention policies
- **Current status:** ✅ Implemented correctly
- **Emre dependency:** He triggers audit logs from handlers, doesn't modify logging logic

### Emre Codes (Safer 70%)
These are **surface area** components where mistakes are local and testable:

#### 1. Web UI (`skill/web/` - to be created)
- **Why Emre:** Frontend is his strength, mistakes are visible immediately
- **What:** React SPA, FastAPI backend, settings page, dashboard widgets
- **Your role:** Review designs, approve API contracts, test on mobile
- **Learning value:** Emre practices full-stack while you practice code review

#### 2. OVOS Intent Handlers (`skill/__init__.py`)
- **Why Emre:** Intent logic is straightforward: parse slots → call dispatcher → return dialog
- **What:** `@intent_handler` methods, slot extraction, dialog selection
- **Your role:** Define intent patterns (`.intent` files), review handler logic
- **Learning value:** Emre learns OVOS, you practice architectural guidance

#### 3. Dialogs & Localization (`skill/locale/en-us/`)
- **Why Emre:** Low-risk linguistic work, iterative refinement
- **What:** `.dialog` files, `.intent` patterns, response templates
- **Your role:** Review for technical accuracy (don't say "algorithm" when meaning "model")
- **Learning value:** Emre understands user-facing layer, you practice content review

#### 4. Test Suite (`tests/`)
- **Why Emre:** Writing tests teaches system behavior without breaking production
- **What:** Unit tests, integration tests, mock fixtures
- **Your role:** Define test strategy, review coverage, pair on complex tests
- **Learning value:** Emre learns testing discipline, you practice test-driven guidance

#### 5. Docker Configuration (`docker/`, `docker-compose.yml`)
- **Why Emre:** DevOps practice, well-documented in architecture
- **What:** Container definitions, volume mounts, network config
- **Your role:** Review security (no exposed secrets), validate production readiness
- **Learning value:** Emre learns deployment, you practice infrastructure review

---

## 🔧 Critical Fix Required: Adapter Interface (DEC-007 Violation)

### What's Wrong?

Current adapter interface in [skill/adapters/base.py](../skill/adapters/base.py):

```python
class ManufacturingAdapter(ABC):
    @abstractmethod
    def get_kpi(self, metric: CanonicalMetric, filters: dict) -> KPIResult:
        """Retrieve single KPI value"""
        pass
    
    @abstractmethod
    def compare(self, metric: CanonicalMetric, entities: list[str]) -> ComparisonResult:
        """Compare metric across entities"""
        pass
    
    @abstractmethod
    def get_trend(self, metric: CanonicalMetric, time_range: str) -> TrendResult:
        """Get metric trend over time"""
        pass
    
    @abstractmethod
    def check_anomaly(self, metric: CanonicalMetric, filters: dict) -> AnomalyResult:
        """❌ WRONG: Adapters should NOT detect anomalies"""
        pass
    
    @abstractmethod
    def simulate_whatif(self, scenario: dict) -> WhatIfResult:
        """❌ WRONG: Adapters should NOT simulate scenarios"""
        pass
```

### Why It's Wrong?

**DEC-007: Intelligence Services Are Platform-Independent**

From [docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md](AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md#L489-L511):

> **Principle:** Anomaly detection and what-if simulation are NOT data-fetching operations. They are intelligence services that should work the same way regardless of whether your data comes from RENERYO, SAP, Siemens, or a CSV file.

**Problem:** By putting `check_anomaly()` and `simulate_whatif()` in the adapter interface:
1. Every adapter (RENERYO, SAP, Siemens) must implement anomaly logic independently
2. You're mixing data transformation (adapter job) with intelligence (service job)
3. PREVENTION service becomes useless - adapters bypass it
4. DocuBoT grounding can't be orchestrated - adapters don't call it

### Correct Architecture

```
User: "Any energy spikes today?"
         ↓
  Intent Handler (Emre codes)
         ↓
  QueryDispatcher (You code) ←────────────────┐
         ↓                                     │
    ┌─────────────────────────────────┐       │
    │ 1. Get raw data via adapter     │       │
    │ 2. Call PREVENTION service      │ ← Intelligence orchestration
    │ 3. Call DocuBoT for context     │       │
    │ 4. Combine into AnomalyResult   │       │
    └─────────────────────────────────┘       │
         ↓                                     │
    Adapter.get_raw_data() ──────────────────┘
         ↓
    RENERYO API / SAP API / CSV file
```

### The Fix (30 Minutes)

**Step 1:** Remove intelligence methods from adapter interface:

```python
# skill/adapters/base.py
class ManufacturingAdapter(ABC):
    @abstractmethod
    def get_kpi(self, metric: CanonicalMetric, filters: dict) -> KPIResult:
        pass
    
    @abstractmethod
    def compare(self, metric: CanonicalMetric, entities: list[str]) -> ComparisonResult:
        pass
    
    @abstractmethod
    def get_trend(self, metric: CanonicalMetric, time_range: str) -> TrendResult:
        pass
    
    @abstractmethod
    def get_raw_data(self, metric: CanonicalMetric, filters: dict) -> pd.DataFrame:
        """NEW: Fetch raw time-series data for intelligence services to analyze"""
        pass
    
    # ❌ REMOVED: check_anomaly(), simulate_whatif()
```

**Step 2:** Update MockAdapter to remove those methods:

```python
# skill/adapters/mock.py
class MockAdapter(ManufacturingAdapter):
    # Remove check_anomaly() and simulate_whatif() implementations
    
    def get_raw_data(self, metric: CanonicalMetric, filters: dict) -> pd.DataFrame:
        """Return mock time-series data"""
        return pd.DataFrame({
            'timestamp': pd.date_range('2026-01-01', periods=100, freq='H'),
            'value': np.random.normal(100, 10, 100),
            'unit': 'kWh' if metric == CanonicalMetric.ENERGY_PER_UNIT else 'units'
        })
```

**Step 3:** Move intelligence to QueryDispatcher (Phase 3 work):

```python
# skill/services/query_dispatcher.py
class QueryDispatcher:
    def check_anomaly(self, metric: CanonicalMetric, filters: dict) -> AnomalyResult:
        # 1. Get raw data from adapter
        raw_data = self.adapter.get_raw_data(metric, filters)
        
        # 2. Call PREVENTION service for anomaly detection
        anomalies = self.prevention_client.detect_anomalies(raw_data)
        
        # 3. Call DocuBoT for context (why did this happen?)
        context = self.docubot_client.explain_anomaly(metric, anomalies)
        
        # 4. Build result
        return AnomalyResult(
            metric=metric,
            anomalies_detected=len(anomalies) > 0,
            anomaly_details=anomalies,
            explanation=context
        )
```

### Impact

- **Phase 1:** You fix adapter interface (this week)
- **Phase 3:** You integrate DocuBoT/PREVENTION (M3-M4)
- **Emre:** Not affected - he uses QueryDispatcher, which keeps same interface

---

## 🗺️ Implementation Roadmap

### Phase 0: Foundation (This Week)

#### Task 1: Team Definition (1-2 hours)
**Owner:** You  
**Deliverable:** This document reviewed and agreed with Emre

**Actions:**
1. ✅ Document created (you're reading it)
2. Schedule meeting with Emre to review work division
3. Agree on communication protocol:
   - Daily standup? (15 min sync)
   - PR review SLA? (within 4 hours?)
   - Blocked task escalation? (Slack DM immediately?)
4. Set up Git workflow:
   - Branch naming: `feature/you-description` vs `feature/emre-description`
   - PR template with checklist
   - Merge policy: Require 1 approval (you review all Emre PRs initially)

**Success Criteria:** Emre understands his 70%, you commit to reviewing within 4 hours

#### Task 2: Fix Adapter Interface (30 minutes)
**Owner:** You  
**Deliverable:** DEC-007 compliant adapter interface

**Actions:**
1. Read [docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md](AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md) DEC-007 section
2. Modify [skill/adapters/base.py](../skill/adapters/base.py):
   - Remove `check_anomaly()` method
   - Remove `simulate_whatif()` method
   - Add `get_raw_data()` method with pandas DataFrame return type
3. Update [skill/adapters/mock.py](../skill/adapters/mock.py):
   - Remove those 2 method implementations
   - Implement `get_raw_data()` returning mock time-series
4. Update [tests/test_adapters/test_mock_adapter.py](../tests/test_adapters/test_mock_adapter.py):
   - Remove anomaly and what-if tests from adapter tests
   - Add `test_get_raw_data()` test
5. Add TODO comment in QueryDispatcher for Phase 3

**Success Criteria:** `pytest tests/test_adapters/ -v` passes, architecture compliance restored

#### Task 3: Update GitHub Agents (1-2 hours)
**Owner:** You  
**Deliverable:** Team-aware Copilot agents

**Actions:**
1. Update [.github/agents/task-planner.agent.md](../.github/agents/task-planner.agent.md):
   - Add team context: "Lead Developer (architecture owner) + Junior Developer (implementation focus)"
   - Add work division rules: "Domain/adapters/orchestration → Lead, UI/intents/tests → Junior"
   - Add PR workflow guidance: "All Junior PRs reviewed by Lead within 4 hours"

2. Update [.github/agents/reviewer.agent.md](../.github/agents/reviewer.agent.md):
   - Add review checklist for Lead reviewing Junior code
   - Add self-review checklist for Junior before submitting PR
   - Add architectural red flags: "Junior modifying adapters → escalate immediately"

3. Update [.github/agents/skill-developer.agent.md](../.github/agents/skill-developer.agent.md):
   - Add: "If coding intent handlers, follow Junior pattern (use QueryDispatcher, don't modify adapters)"
   - Add: "If coding adapters, follow Lead pattern (extend ManufacturingAdapter ABC)"

4. Create [.github/agents/onboarding-emre.agent.md](../.github/agents/onboarding-emre.agent.md):
   - AVAROS quickstart for new team member
   - Architecture overview (5-min version)
   - "What you own" checklist
   - "What to ask Lead about" checklist

5. Update [.github/copilot-instructions.md](../.github/copilot-instructions.md):
   - Add team section with work division
   - Update examples to show Lead vs Junior coding patterns

**Success Criteria:** Copilot suggests appropriate patterns based on file being edited

### Phase 1: Parallel Development (M1-M2)

#### You Build (M1-M2)
1. **Domain Enhancements:** Add missing CanonicalMetric enums (if any)
2. **RENERYO Adapter:** Implement first real adapter (RENERYO API integration)
3. **Settings Service:** Migrate SQLite to PostgreSQL for production
4. **Audit Service:** Validate GDPR compliance with test scenarios
5. **QueryDispatcher Phase 1:** Basic routing without DocuBoT/PREVENTION

#### Emre Builds (M1-M2)
1. **Web UI Foundation:** FastAPI + React project setup
2. **Settings Page:** Configure RENERYO connection via Web UI
3. **KPI Dashboard:** Display energy_per_unit, scrap_rate, oee
4. **Intent Handlers:** Implement all 15 intents from locale/ files
5. **Test Suite:** Write unit tests for intent handlers

#### Your Leadership Practice (M1-M2)
- **Code Review:** Review every Emre PR within 4 hours
- **Daily Check-in:** 15-min sync on blockers
- **Pair Programming:** 2 sessions/week on complex topics (1 hour each)
- **Architecture Q&A:** Answer "why not this way?" questions patiently
- **Git Rescue:** Help when Emre has merge conflicts

### Phase 2: Integration (M2-M3)

#### You Build
1. **Integration Tests:** Adapter + Dispatcher + Intent end-to-end tests
2. **Error Handling:** Graceful degradation when RENERYO unavailable
3. **Multi-Adapter Support:** Adapter factory selects RENERYO vs Mock
4. **Docker Expansion:** Add postgres, redis containers

#### Emre Builds
1. **UI Polish:** Responsive design, loading states, error messages
2. **Data Ingestion UI:** Configure MQTT/OPC-UA via Web UI
3. **Dashboard Widgets:** Add comparison and trend visualizations
4. **Localization:** Add Turkish locale files
5. **E2E Tests:** Cypress/Playwright for Web UI

#### Your Leadership Growth
- **Delegation:** Let Emre own entire features (e.g., "Turkish localization is 100% yours")
- **Trust Building:** Reduce PR review scrutiny for low-risk files (dialogs, CSS)
- **Conflict Navigation:** Practice giving critical feedback constructively
- **Emre's Career:** Help him identify what he wants to specialize in

### Phase 3: Intelligence Layer (M3-M4)

#### You Build (Critical - Can't Delegate)
1. **DocuBoT Integration:** RAG retrieval for procedure grounding
2. **PREVENTION Integration:** Anomaly detection service calls
3. **QueryDispatcher Phase 3:** Orchestrate check_anomaly() using DocuBoT + PREVENTION
4. **What-If Orchestration:** Integrate simulation logic with adapters

#### Emre Builds (Supporting Role)
1. **Anomaly UI:** Display anomaly alerts with DocuBoT explanations
2. **What-If UI:** Interactive scenario builder
3. **Test Mocks:** Mock DocuBoT/PREVENTION responses for testing
4. **Documentation:** User guide for anomaly investigation workflow

---

## 🎓 Leadership Skills You'll Learn

### Month 1-2: Fundamentals
- ✅ Task breakdown: Divide features into you/Emre subtasks
- ✅ Code review: Spot issues without discouraging learning
- ✅ Git workflow: Manage branches, resolve conflicts, enforce standards
- ✅ Communication: Daily sync, PR feedback, architecture explanations

### Month 3-4: Delegation
- ✅ Trust calibration: Know when to review deeply vs trust Emre
- ✅ Failure management: Let Emre make mistakes on low-risk tasks
- ✅ Knowledge transfer: Pair program to teach, not just fix
- ✅ Scope control: Say "no" to Emre's over-engineering ideas

### Month 5-6: Strategic Thinking
- ✅ Priority balancing: Technical debt vs new features
- ✅ Career development: Help Emre grow into areas he's passionate about
- ✅ Stakeholder management: Report progress to manager clearly
- ✅ Team scaling: Ready to onboard Developer #3 if needed

### Month 7+: Ready for HEDGE
- ✅ **Now** you can manage Emre on HEDGE while you code AVAROS
- ✅ **Or** both of you tackle HEDGE together with established workflow
- ✅ You've proven leadership capability to manager

---

## 🚨 Common Pitfalls to Avoid

### Pitfall 1: Treating Emre as Copilot Agent
**Symptom:** "Go implement feature X" with no context  
**Fix:** Provide architecture diagram, point to similar code, pair on first task

### Pitfall 2: Coding Everything Yourself
**Symptom:** "Faster if I just do it" mentality  
**Fix:** Accept 2x time in Month 1 to build 5x team velocity in Month 6

### Pitfall 3: Perfectionist PR Reviews
**Symptom:** 30 comments on variable naming in test files  
**Fix:** Focus on architectural issues, let style guide handle formatting

### Pitfall 4: Avoiding Difficult Conversations
**Symptom:** Emre's code has fundamental flaw, you merge to avoid conflict  
**Fix:** "This breaks DEC-007, here's why, let's pair to fix it" (teach, don't blame)

### Pitfall 5: No Celebration
**Symptom:** Emre finishes Web UI, you immediately assign next task  
**Fix:** "This dashboard looks great! Show it in next team meeting."

---

## 📊 Success Metrics

### Month 2 Checkpoint
- [ ] Adapter interface fixed (DEC-007 compliant)
- [ ] Emre has merged 10+ PRs (UI, intents, tests)
- [ ] You've reviewed 100% of PRs within 4-hour SLA
- [ ] Zero critical bugs in production (mock mode)
- [ ] Emre can explain AVAROS architecture to outsider

### Month 4 Checkpoint
- [ ] RENERYO adapter working with real API
- [ ] Web UI deployed and usable by non-developers
- [ ] You've delegated entire features to Emre without code review
- [ ] Emre has identified and fixed architectural issue independently
- [ ] Manager observes: "You're leading, not just coding"

### Month 6 Checkpoint (AVAROS Phase 1-2 Complete)
- [ ] All 15 intents working end-to-end
- [ ] DocuBoT and PREVENTION integrated
- [ ] Test coverage >80%
- [ ] Emre is onboarding Developer #3 (you observe, don't intervene)
- [ ] **You're ready to lead HEDGE project from Day 1**

---

## 🎯 Final Recommendation

**Choose Modified Option B.** Learn leadership on AVAROS where you have deep technical confidence. Practice code review, task delegation, and conflict resolution on familiar ground. After 6 months, you'll have both:

1. **Technical Output:** Production-ready AVAROS with Emre as co-developer
2. **Leadership Proof:** Demonstrated ability to manage, delegate, review, and scale

**Then** consider HEDGE. But by then, you won't be asking "should I give it to Emre?" — you'll be confident planning "how WE tackle HEDGE together."

---

## 📎 Next Steps

1. **Right now:** Read this document fully
2. **Today:** Schedule 1-hour meeting with Emre to review this plan
3. **Tomorrow:** Start "Task 2: Fix Adapter Interface" (30 minutes)
4. **This week:** Complete Phase 0 (Foundation)
5. **Next week:** Start Phase 1 parallel development

**Questions?** Ask them. Leadership is learned, not innate. Every senior developer was once in your position.

---

*This is your roadmap. Adapt it as you learn. The goal isn't perfection — it's progress.*
