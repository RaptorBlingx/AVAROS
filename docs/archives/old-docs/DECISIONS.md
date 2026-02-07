# AVAROS Decision Log

**Purpose:** Record all architectural and implementation decisions with rationale.  
**Why:** Agents have limited memory. This log ensures decisions aren't forgotten or contradicted.

---

## Decision Record Format

Each decision follows this template:

```
### DEC-XXX: [Short Title]
**Date:** YYYY-MM-DD  
**Status:** ✅ Accepted | 🔄 Under Review | ❌ Rejected | ⚠️ Superseded by DEC-YYY  
**Decided By:** [Agent Name]  
**Context:** Why was this decision needed?  
**Decision:** What was decided?  
**Rationale:** Why this choice over alternatives?  
**Alternatives Considered:**  
1. Alternative A - rejected because...
2. Alternative B - rejected because...  
**Consequences:** What are the implications?
```

---

## Decisions

### DEC-001: Platform-Agnostic Adapter Pattern
**Date:** 2026-01-29  
**Status:** ✅ Accepted  
**Decided By:** Project Inception (WASABI Proposal)  
**Context:** AVAROS must work with multiple manufacturing platforms (RENERYO, future platforms) without code changes.  
**Decision:** Use the Adapter Pattern with a ManufacturingAdapter abstract base class. AVAROS skill code never references specific platforms.  
**Rationale:** 
- Golden Rule: "AVAROS understands manufacturing; Adapters understand platforms"
- Enables selling to customers on any platform
- Clean separation of concerns
**Alternatives Considered:**
1. Direct API integration - rejected (vendor lock-in)
2. Plugin system - rejected (more complex for our use case)
**Consequences:** 
- Each new platform requires a new adapter implementation
- Testing requires MockAdapter
- Configuration must be runtime-switchable

---

### DEC-002: Five Query Types Only
**Date:** 2026-01-29  
**Status:** ✅ Accepted  
**Decided By:** Project Inception (WASABI Proposal)  
**Context:** Voice interfaces need bounded, predictable interaction patterns.  
**Decision:** All manufacturing queries must map to exactly 5 types: get_kpi, compare, get_trend, check_anomaly, simulate_whatif.  
**Rationale:**
- Cognitive load: users can learn 5 patterns easily
- Implementation scope: bounded adapter interface
- Testability: finite test matrix
**Alternatives Considered:**
1. Free-form queries with NLU - rejected (unpredictable, hard to test)
2. More query types - rejected (scope creep, WASABI deliverables are fixed)
**Consequences:**
- New features must fit into these 5 types
- May need to expand post-WASABI

---

### DEC-003: Zero-Config Deployment
**Date:** 2026-01-29  
**Status:** ✅ Accepted  
**Decided By:** Project Inception (WASABI Proposal)  
**Context:** Target users are factory operators, not DevOps engineers.  
**Decision:** `git clone && docker compose up` must result in a working demo system (with MockAdapter).  
**Rationale:**
- Reduces barrier to evaluation
- Demo at conferences/trade shows
- First-run wizard handles real platform setup
**Alternatives Considered:**
1. Require manual config files - rejected (bad UX)
2. SaaS-only deployment - rejected (factories want on-premise)
**Consequences:**
- MockAdapter is mandatory
- SettingsService reads from database, not files
- Web UI required for configuration

---

### DEC-004: Immutable Domain Models (Frozen Dataclasses)
**Date:** 2026-01-30  
**Status:** ✅ Accepted  
**Decided By:** AVAROS Architect  
**Context:** Domain models are shared across layers and passed through async boundaries. Mutable state causes bugs.  
**Decision:** All domain models use `@dataclass(frozen=True)` for immutability. Lists converted to tuples in `__init__`.  
**Rationale:**
- Prevents accidental mutation
- Thread-safe by design
- Easier to reason about data flow
- Required for hashability (caching)
**Alternatives Considered:**
1. Pydantic models - rejected (heavier dependency, frozen mode less ergonomic)
2. Named tuples - rejected (less readable, no methods)
**Consequences:**
- Cannot modify results after creation (intentional)
- Must create new instances for changes
- Slightly more verbose initialization for nested lists

---

### DEC-005: Async Adapter Interface with Sync Wrapper
**Date:** 2026-01-30  
**Status:** ✅ Accepted  
**Decided By:** AVAROS Architect  
**Context:** Platform APIs are I/O-bound. OVOS handlers are synchronous.  
**Decision:** ManufacturingAdapter methods are `async`. QueryDispatcher provides sync wrappers using `asyncio.run()`.  
**Rationale:**
- Async enables concurrent API calls (batch queries)
- Sync wrapper maintains OVOS compatibility
- Future-proofs for async OVOS versions
**Alternatives Considered:**
1. All sync - rejected (blocks on I/O)
2. All async throughout - rejected (OVOS not async-native)
**Consequences:**
- Slight overhead from event loop creation
- Need to handle nested event loops carefully

---

### DEC-006: Query Dispatcher as Facade
**Date:** 2026-01-30  
**Status:** ✅ Accepted  
**Decided By:** AVAROS Architect  
**Context:** Intent handlers need simple interface to adapters with audit logging.  
**Decision:** QueryDispatcher acts as a Facade between skill handlers and adapters, handling async bridging and audit logging.  
**Rationale:**
- Single point for audit logging (GDPR)
- Encapsulates async complexity
- Easy to add cross-cutting concerns (caching, retries)
**Alternatives Considered:**
1. Direct adapter calls from handlers - rejected (scattered audit logic)
2. Decorator-based approach - rejected (less explicit)
**Consequences:**
- All queries go through dispatcher
- Slight indirection, but cleaner separation

---

### DEC-007: Three-Sprint Development Plan
**Date:** 2026-01-30  
**Status:** ✅ Accepted  
**Decided By:** AVAROS Task Planner  
**Context:** With 70% scaffolding complete, need to organize remaining ~50 tasks into manageable sprints with clear parallel work opportunities.  
**Decision:** Three sprints: (1) MVP Foundation with MockAdapter + CI/CD (2-3 days), (2) RENERYO Integration (5-7 days), (3) Polish & Enhancement (7-10 days).  
**Rationale:**
- Sprint 1 establishes testing foundation and CI/CD early
- Sprint 2 delivers first real platform integration (proposal requirement)
- Sprint 3 adds advanced features without blocking MVP
- Each sprint has parallel work groups (Skill Dev + Testing + DevOps)
**Alternatives Considered:**
1. Single linear sprint - rejected (no parallelization, slower)
2. Feature-based sprints - rejected (dependencies not clear)
**Consequences:**
- With parallel agents, Sprint 1 completes in 2 days vs 4 days solo
- RENERYO adapter becomes MVP milestone
- Web UI deferred to post-MVP (acceptable)

---

### DEC-008: *(Reserved for Implementation)*
**Date:**  
**Status:** 🔄 Under Review  
**Decided By:**  
**Context:**  
**Decision:**  
**Rationale:**  
**Alternatives Considered:**  
**Consequences:**  

---

### DEC-005: *(Reserved for Architect)*
*(Add more as needed)*

---

## Quick Decision Index

| ID | Title | Status | Category |
|----|-------|--------|----------|
| DEC-001 | Platform-Agnostic Adapter Pattern | ✅ | Architecture |
| DEC-002 | Five Query Types Only | ✅ | Architecture |
| DEC-003 | Zero-Config Deployment | ✅ | DevOps |

---

## How to Add Decisions

1. Copy the template above
2. Fill in all fields (don't skip Alternatives or Consequences)
3. Assign next DEC-XXX number
4. Update the Quick Decision Index

**Important:** Agents must check this file before making decisions that might contradict existing ones!
