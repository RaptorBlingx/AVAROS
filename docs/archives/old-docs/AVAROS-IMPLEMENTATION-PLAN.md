# AVAROS Implementation Plan & Development Roadmap

> **Developer's Guide to Building the AVAROS System**
>
> This document demonstrates complete understanding of the AVAROS project architecture and provides a detailed implementation plan aligned with the WASABI 2 Open Call proposal.

**Document Purpose:** Technical implementation blueprint for development team
**Alignment:** WASABI 2 Call Proposal - Work Packages 0-5
**Timeline:** M1-M12 (12 months)
**Developer:** ArtıBilim Software Team

---

## Table of Contents

1. [Project Understanding](#1-project-understanding)
2. [System Architecture](#2-system-architecture)
3. [Work Package Breakdown](#3-work-package-breakdown)
4. [Development Sprint Plan](#4-development-sprint-plan)
5. [Technical Implementation Details](#5-technical-implementation-details)
6. [Integration Strategy](#6-integration-strategy)
---

## 1. Project Understanding

### 1.1 Project Objectives (From WASABI Proposal)

**Primary Goal:** Design, implement, and validate an OVOS-based digital assistant that consolidates distributed supply chain data and supports manufacturing planning optimization through conversational AI.

**Target Outcomes:**
- ≥8% reduction in electricity per unit
- ≥5% improvement in material efficiency
- ≥10% decrease in CO₂-eq emissions
- TRL advancement through dual-pilot validation
- Publication on WASABI White-Label Shop

### 1.2 Technical Scope

AVAROS consists of **five integrated components**:

| Component | Source | Purpose |
|-----------|--------|---------|
| **OVOS Skill** | ArtıBilim Development | Conversational interface, intent handling |
| **OVOS Core** | WASABI Stack | Voice assistant framework (STT/TTS/message bus) |
| **DocuBoT** | WASABI Stack | Document retrieval and grounding (RAG) |
| **PREVENTION** | WASABI Stack | Anomaly detection and drift warnings |
| **RENERYO Adapter** | ArtıBilim Development | Platform integration layer |

**Our Responsibility (ArtıBilim):**
- Develop AVAROS Skill (intent handlers, dialog, response formatting)
- Implement RENERYO Adapter (API integration)
- Integrate DocuBoT and PREVENTION services (REST clients)
- Create Docker-Compose orchestration
- Implement SettingsService, AuditLogger, QueryDispatcher
- Web UI for configuration

**WASABI Team Responsibility:**
- Provide OVOS, DocuBoT, PREVENTION containers
- Configuration guidance for stack components
- Shop publication support

### 1.3 Key Architectural Decisions

| Decision ID | Decision | Rationale |
|-------------|----------|-----------|
| **DEC-001** | Platform-agnostic adapter pattern | RENERYO is first, not only platform |
| **DEC-002** | Five query types only | Bounded interaction for voice UX |
| **DEC-003** | Zero-config with MockAdapter | Demo works immediately after `docker compose up` |
| **DEC-004** | Database-backed configuration | No file editing, hot-reload |
| **DEC-005** | Clean Architecture (4 layers) | Separation of concerns, testability |
| **DEC-006** | Immutable domain models | Thread safety, predictability |

---

## 2. System Architecture

### 2.1 Complete System Diagram

(Architecture diagram showing the complete system including User Interface, OVOS Core, AVAROS Skill with Presentation, Use Case, and Adapter layers, and external services including DocuBoT, PREVENTION, RENERYO Platform, and other EnMS platforms)

### 2.2 Component Responsibility Matrix

| Component | Layer | What We Build | What WASABI Provides |
|-----------|-------|---------------|----------------------|
| **OVOS Core** | Infrastructure | - | ✅ Container, STT/TTS engines, message bus |
| **Intent Files** | Presentation | ✅ .intent files for 5 query types | - |
| **Dialog Files** | Presentation | ✅ .dialog response templates | - |
| **Intent Handlers** | Presentation | ✅ Python methods in skill | - |
| **Response Builder** | Presentation | ✅ Format results to voice | - |
| **Query Dispatcher** | Use Case | ✅ Route + orchestrate | - |
| **Audit Logger** | Use Case | ✅ GDPR-compliant logging | - |
| **Settings Service** | Use Case | ✅ Config management | - |
| **Adapter Factory** | Adapter | ✅ Registry + lifecycle | - |
| **MockAdapter** | Adapter | ✅ Demo data generator | - |
| **RENERYOAdapter** | Adapter | ✅ API integration | - |
| **DocuBoT Client** | Adapter | ✅ REST client wrapper | ✅ DocuBoT service |
| **PREVENTION Client** | Adapter | ✅ REST client wrapper | ✅ PREVENTION service |
| **Docker-Compose** | Infrastructure | ✅ Orchestration file | ✅ Base images |
| **Web UI** | Infrastructure | ✅ Settings configuration | - |

### 2.3 Data Flow Architecture

**Query Lifecycle (Detailed):**

(Detailed flow diagram showing 7 phases: User Input → Intent Recognition → Intent Handler → Query Dispatch → Adapter Execution → Response Formatting → Speech Output, with step-by-step processing at each phase)

---

## 3. Work Package Breakdown

### WP0: Project Management & Quality

**Duration:** M1 - M12
**Lead:** ArtıBilim
**My Role:** Development coordination, technical documentation

| Task | Developer Activities | Deliverables |
|------|---------------------|--------------|
| **T0.1** Coordination | Attend bi-weekly meetings, update task status | - |
| **T0.2** Monitoring | Prepare demo for M2/M4/M6/M8/M10 monitoring | Live system demos |
| **T0.3** Documentation | Maintain technical docs, architecture decisions | This document |

**Developer Milestones:**
- M2: Alpha demo ready
- M4: Core features complete
- M6: Beta with RENERYO integration
- M8: Pilot deployment
- M10: KPI measurement
- M12: Final release

---

### WP1: Requirements, Data Readiness & Architecture

**Duration:** M1 - M2
**Lead:** ArtıBilim
**My Role:** System architect, technical lead

#### T1.1: Use-Case Scoping and KPI Baselines

**Developer Tasks:**
1. Map WASABI KPI targets to canonical metrics:
   - Electricity per unit → `ENERGY_PER_UNIT`
   - Material efficiency → `MATERIAL_EFFICIENCY`, `SCRAP_RATE`
   - CO₂-eq → `CO2_PER_UNIT`, `CO2_TOTAL`

2. Define the 5 query types with examples:
   - GET_KPI: "What's our OEE?"
   - COMPARE: "Compare suppliers"
   - GET_TREND: "Energy trend"
   - CHECK_ANOMALY: "Any problems?"
   - SIMULATE_WHATIF: "What if...?"


#### T1.2: Data Source Inventory

**Developer Tasks:**
1. Survey RENERYO API:
   - Endpoint: `/api/v1/kpi/*`
   - Authentication: Bearer token
   - Response format: JSON
   - Rate limits: 100 req/min

2. Identify required data for each query type:
   - GET_KPI: Single metric endpoint
   - COMPARE: Batch query endpoint
   - GET_TREND: Time-series endpoint
   - ANOMALY: PREVENTION webhook
   - WHATIF: Simulation model (future)

3. Create RENERYO → Canonical mapping table

**Deliverable:** `config/adapters/reneryo-mapping.yaml`

#### T1.3: Security & Governance Setup

**Developer Tasks:**
1. Implement GDPR-compliant audit logger with immutable log entries containing timestamp, query_id, user_role (not user_id to avoid PII), intent, data_accessed list, and optional recommendation_id.

2. Implement encrypted credential storage (Fernet)

3. Role-based access control (RBAC):
   - Operator: Read-only queries
   - Planner: + What-if simulations
   - Admin: + Configuration

**Deliverable:** `skill/services/audit.py`, `skill/services/security.py`

#### T1.4: Technical Architecture & Connector Plan

**Developer Tasks:**
1. Define layer boundaries:
   - skill/__init__.py: Presentation layer
   - skill/use_cases/: Business logic layer
   - skill/adapters/: External integrations layer
   - skill/domain/: Pure domain models layer

2. Specify communication protocols:
   - OVOS ↔ Skill: Message bus (internal)
   - Skill ↔ RENERYO: HTTPS REST/JSON
   - Skill ↔ DocuBoT: HTTPS REST/JSON
   - Skill ↔ PREVENTION: HTTPS REST/JSON + Webhook

3. Design adapter interface with abstract methods for get_kpi returning KPIResult, compare returning CompareResult, and other query types.

**Deliverable:** `docs/ARCHITECTURE.md` (completed), `skill/adapters/base.py`

#### T1.5: Experiment Handbook v0.1

**Developer Tasks:**
- Document baseline architecture
- Record technical decisions (DECISIONS.md)
- Create development checklist

**Deliverable:** `docs/EXPERIMENT-HANDBOOK-TEMPLATE.md`

#### T1.6: IPR Plan

**Developer Tasks:**
- Clarify open-source vs proprietary boundaries:
  - AVAROS Skill: Open source (permissive license)
  - RENERYO core: Proprietary
  - Adapters: Open templates

**Deliverable:** `docs/IPR-PLAN.md`

---

### WP2: DIA Development (OVOS + DocuBoT + PREVENTION)

**Duration:** M1 - M6
**Lead:** ArtıBilim
**My Role:** Lead developer

#### T2.1: OVOS Intents/Dialogue/What-If Flows

**Development Tasks:**

**Month 1-2: Intent Files**

Create intent files in skill/locale/en-us/ directory for all query types:
- KPI intents: energy per unit, OEE, scrap rate
- Comparison intents: supplier, asset
- Trend intents: energy, quality
- Anomaly intent: check
- What-if intent: supplier change

Example intent file patterns include variations for natural language queries with placeholders for period, asset, and other entities.

**Month 2-3: Dialog Files**

Create dialog templates for responses with placeholders for dynamic values like period, value, unit, delta, direction, and asset.

**Month 3-4: Intent Handlers**

Implement AVAROSSkill class extending OVOSSkill with initialize method to register intent files and handler methods. Each handler extracts parameters from message data, calls query dispatcher with appropriate canonical metrics and time periods, and speaks dialog with formatted results.

**Deliverable:** `skill/__init__.py`, `skill/locale/` (complete)

#### T2.2: DocuBoT Indexing Pipeline

**Development Tasks:**

**Month 3: DocuBoT Client**

Implement DocuBotClient class with async methods for querying DocuBoT service with questions and top_k parameter, returning DocuBotResponse objects, and uploading documents for indexing.

**Month 3-4: PREVENTION Client**

Implement PREVENTIONClient class with async methods for checking anomalies in metrics over time periods, returning AnomalyResult objects, and registering webhook callbacks for proactive alerts.

**Deliverable:** `skill/adapters/docubot.py`, `skill/adapters/prevention.py`

#### T2.3: Docker-Compose Stack

**Development Tasks:**

**Month 4-5: Container Orchestration**

Create docker-compose.yml file defining services for:
- ovos-core: OVOS framework with STT/TTS engines and message bus
- avaros-skill: Custom skill service
- docubot: DocuBoT RAG service
- prevention: PREVENTION anomaly detection service
- postgres: Database for settings and audit logs
- web-ui: Configuration web interface

Include volume mounts for persistent data and appropriate service dependencies.

**Deliverable:** `docker-compose.yml`, `Dockerfile`

#### T2.4: Validation on ArtıBilim Testbed

**Development Tasks:**

**Month 5-6: Integration Testing**
1. Deploy to ArtıBilim plastics/toy site
2. Connect to RENERYO development instance
3. Test each query type with real data
4. Measure response latency (<3 seconds target)
5. Voice recognition accuracy testing (>90% target)
6. Multi-turn conversation testing

**Test Scenarios:**

Create integration tests to verify full stack functionality including:
- Simulating voice input through OVOS
- Verifying intent recognition and matching
- Checking skill handler execution
- Validating adapter calls
- Confirming response content

**Deliverable:** Test report, performance metrics

---

### WP3: Integration & Dual Pilots

**Duration:** M5 - M10
**Lead:** ArtıBilim (Co-lead: AI EDIH TÜRKIYE)
**My Role:** Deployment engineer, pilot support

#### T3.1: Pilot Implementation Plan

**Development Tasks:**

**Month 5: Pilot Setup**
1. Document deployment requirements:
   - Hardware: 4GB RAM minimum, x86_64 or ARM64
   - Network: HTTPS access to RENERYO, DocuBoT, PREVENTION
   - Ports: 8080 (Web UI), 8181 (OVOS message bus)

2. Create deployment playbook covering:
   - Cloning the repository
   - Configuring environment variables
   - Starting the Docker compose stack
   - Waiting for health checks
   - Running first-time setup wizard

3. Operator training materials

**Deliverable:** Deployment guide, training videos

#### T3.2: Parallel Deployment

**Development Tasks:**

**Month 6-8: Pilot Site A (DIH-Designated Factory)**
- Remote deployment support
- Monitor logs via centralized logging (ELK stack)
- Weekly check-ins with operators

**Month 6-8: Pilot Site B (MEXT Digital Factory)**
- On-site deployment
- Integration with digital twin
- Demonstration sessions

**Monitoring Dashboard:**

Implement web monitoring dashboard showing:
- Total queries executed
- Average response time
- Top intents by frequency
- Error rate metrics
- KPI trend calculations

**Deliverable:** Deployed systems, monitoring setup

#### T3.3: KPI Baselines and Endlines

**Development Tasks:**

**Month 6: Baseline Measurement**
1. Capture pre-AVAROS metrics (2-week period):
   - Energy per unit (kWh)
   - Material efficiency (%)
   - CO₂-eq per unit (kg)
   - Decision latency (minutes from data to action)

2. Store in database for comparison

**Month 8-9: Midline Tuning**
- Adjust dialog templates based on user feedback
- Tune PREVENTION thresholds
- Optimize adapter caching

**Month 10: Endline Measurement**
1. Capture post-AVAROS metrics (2-week period)
2. Calculate improvements using baseline and endline measurements to determine percentage changes. Target for energy improvement: ≤ -8% (reduction).

**Deliverable:** KPI measurement report with statistical significance

#### T3.4: Validation Workshops

**Development Tasks:**
- Prepare demo scripts
- Collect user feedback via surveys
- Document pain points and feature requests
- Implement critical fixes

**Deliverable:** User feedback report, action items

---

### WP4: Packaging & WASABI Shop Publication

**Duration:** M11 - M12
**Lead:** ArtıBilim
**My Role:** Release engineer

#### T4.1: Dockerized Release

**Development Tasks:**

**Month 11: Release Preparation**
1. Version tagging: `v1.0.0`
2. Multi-arch Docker images (amd64, arm64)
3. Create minimal "getting-started" dataset with sample KPIs, suppliers, documents, and README in data/sample/ directory.

4. Installation checklist covering:
   - Prerequisites: Docker 20.10+, Docker Compose 2.0+, 4GB RAM, required ports
   - Installation steps: clone, configure environment, credentials, docker compose up, setup wizard
   - Verification: test MockAdapter demo mode, voice input, all 5 query types

5. Screenshots and demo videos

**Deliverable:** Docker Hub images, installation package

#### T4.2: Shop Listing

**Development Tasks:**

**Month 11-12: WASABI Shop Publication**
1. Create Shop metadata defining:
   - Name, tagline, and category
   - Keywords: OVOS, EnMS, ISO 50001, Supply Chain, Anomaly Detection
   - Version, license (Apache-2.0), authors
   - Required services: OVOS Core, DocuBoT, PREVENTION
   - Demo URL

2. Write Shop description (non-technical for SMEs)
3. Upload to WASABI Shop

**Deliverable:** Published Shop listing

#### T4.3: Experiment Handbook Final

**Development Tasks:**
- Finalize technical documentation
- Include lessons learned
- Document common pitfalls and solutions
- Create exploitation plan

**Deliverable:** `docs/EXPERIMENT-HANDBOOK-FINAL.md`

---

### WP5: Dissemination & Replication

**Duration:** M3 - M12
**Lead:** AI EDIH TÜRKIYE
**My Role:** Technical support for demos

**Developer Support Tasks:**
- Prepare demo scripts for workshops
- Provide technical Q&A during SME clinics
- Create adapter development tutorial
- Support ≥5 SME onboarding calls post-publication

---

## 4. Development Sprint Plan

### Sprint Structure

- **Sprint Duration:** 2 weeks
- **Total Sprints:** 24 (M1-M12)
- **Team Size:** 3 developers + 1 DevOps

### Sprint Breakdown by Phase

#### Phase 1: Foundation (Sprints 1-8, M1-M4)

**Sprint 1-2: Domain & Architecture**
- [ ] Define canonical metrics enum
- [ ] Implement result types (KPIResult, TrendResult, etc.)
- [ ] Create ManufacturingAdapter interface
- [ ] Set up project structure

**Sprint 3-4: MockAdapter & Core Services**
- [ ] Implement MockAdapter with realistic data
- [ ] Build QueryDispatcher with routing logic
- [ ] Implement AuditLogger (GDPR-compliant)
- [ ] Create SettingsService with encryption

**Sprint 5-6: OVOS Skill Basics**
- [ ] Create intent files (5 query types × 3 variations each)
- [ ] Create dialog files
- [ ] Implement intent handlers (skeleton)
- [ ] Set up OVOS development environment

**Sprint 7-8: Response Builder & Testing**
- [ ] Implement ResponseBuilder (voice formatting)
- [ ] Unit tests for domain models (>80% coverage)
- [ ] Integration tests for QueryDispatcher
- [ ] End-to-end test with MockAdapter

**Milestone M2:** Alpha Demo - MockAdapter fully functional

#### Phase 2: Integration (Sprints 9-12, M4-M6)

**Sprint 9-10: RENERYO Adapter**
- [ ] Map RENERYO API endpoints to canonical metrics
- [ ] Implement authentication flow
- [ ] Implement get_kpi() method
- [ ] Implement compare() method

**Sprint 11-12: DocuBoT & PREVENTION Clients**
- [ ] Build DocuBoT REST client
- [ ] Build PREVENTION REST client
- [ ] Implement webhook handler for proactive alerts
- [ ] Implement get_trend() and check_anomaly()

**Milestone M4:** Core features complete, RENERYO integration started

**Sprint 13-14: What-If Simulation**
- [ ] Design simulation models (heuristic-based)
- [ ] Implement simulate_whatif() in MockAdapter
- [ ] Implement simulate_whatif() in RENERYOAdapter
- [ ] Add what-if intent and dialogs

**Sprint 15-16: Docker-Compose & Deployment**
- [ ] Create docker-compose.yml
- [ ] Implement health checks
- [ ] Create deployment scripts
- [ ] Test full stack deployment

**Milestone M6:** Beta Release - Full stack ready for pilots

#### Phase 3: Deployment (Sprints 17-20, M6-M10)

**Sprint 17-18: Pilot Deployment**
- [ ] Deploy to Pilot Site A (remote)
- [ ] Deploy to Pilot Site B (MEXT)
- [ ] Set up monitoring and logging
- [ ] Operator training sessions

**Sprint 19-20: KPI Measurement & Tuning**
- [ ] Baseline KPI capture
- [ ] Midline measurement
- [ ] Performance optimization (caching, indexing)
- [ ] Bug fixes from pilot feedback

**Milestone M8:** Pilots operational, collecting data

**Milestone M10:** KPI endline measurement complete

#### Phase 4: Release (Sprints 21-24, M10-M12)

**Sprint 21-22: Web UI & Polish**
- [ ] Build configuration Web UI
- [ ] Implement adapter hot-reload
- [ ] Multi-language support (EN, DE, TR)
- [ ] Accessibility improvements

**Sprint 23-24: Packaging & Publication**
- [ ] Create Shop package
- [ ] Write documentation
- [ ] Record demo videos
- [ ] Publish to WASABI Shop

**Milestone M12:** Public release on WASABI Shop

---

## 5. Technical Implementation Details

### 5.1 Domain Models

**File:** `skill/domain/models.py`

(Implementation defines CanonicalMetric enum with universal manufacturing metrics including Energy, Material, Supplier, Production, and Carbon categories. Also includes TimePeriod dataclass with factory methods for common time ranges and string parsing.)

### 5.2 Result Types

**File:** `skill/domain/results.py`

(Implementation defines immutable dataclasses for different result types:
- KPIResult: Single metric value with query_id, timestamp, metric, value, unit, optional asset_id, delta percentage, and confidence
- CompareResult: Comparison between entities with list of entity/value tuples, winner identification, and unit
- Similar classes for TrendResult, AnomalyResult, and WhatIfResult

Each includes to_dict() method for dialog template formatting.)

### 5.3 Query Dispatcher

**File:** `skill/use_cases/query_dispatcher.py`

(Implementation defines QueryDispatcher class for central orchestration of all queries. Key responsibilities:
- Create audit entries with unique query IDs
- Get active adapter from factory
- Execute async adapter calls synchronously using event loop
- Log query success or errors
- Implement get_kpi method and similar methods for compare, get_trend, etc.)

### 5.4 RENERYO Adapter

**File:** `skill/adapters/reneryo.py`

(Implementation defines RENERYOAdapter class implementing ManufacturingAdapter interface:
- Initialize with config containing API URL and encrypted API key
- Create aiohttp session with Bearer token authentication
- Load metric mapping from configuration file
- Implement async get_kpi method that:
  - Maps canonical metrics to RENERYO endpoints
  - Builds requests with date range parameters
  - Executes with retry logic and exponential backoff
  - Maps responses to canonical KPIResult format
- Helper methods for request retry and metric mapping)

**Mapping Config:** `config/adapters/reneryo-mapping.yaml`

(Configuration file mapping canonical metrics to RENERYO API endpoints, specifying endpoint paths, value field names, delta field names, and units for all 20 metrics including ENERGY_PER_UNIT, OEE, etc.)

---

## 6. Integration Strategy

### 6.1 WASABI Component Integration

**DocuBoT Integration:**

(Implementation of DocuBotClient class with async query method that sends questions to DocuBoT service with configurable top_k and min_confidence parameters, receives document-grounded answers with source citations, and formats responses with document names and page numbers.)

**PREVENTION Integration:**

(Implementation of PREVENTIONClient class with:
- Initialization with base URL and webhook URL
- Async check_anomaly method for on-demand anomaly detection
- Webhook registration for proactive alerts
- Returns AnomalyResult objects with detected anomalies including metric, timestamp, value, expected value, and severity)

**Webhook Handler in AVAROS Skill:**

(Implementation adds FastAPI webhook server to AVAROS skill that:
- Runs in background thread
- Receives POST requests from PREVENTION service
- Handles alerts by severity: CRITICAL alerts interrupt current conversation, WARNING alerts queue for next interaction)

### 6.2 Error Handling Strategy

(Implementation defines exception hierarchy with AVAROSError base class, AdapterError for platform communication failures, and ValidationError for invalid input. Intent handlers implement try-catch blocks to:
- Handle validation errors with specific error dialogs
- Fall back to MockAdapter when platform unavailable
- Log unexpected errors and show generic error dialog)

---

## 7. DocuBoT & PREVENTION Workflows

This section provides detailed, step-by-step workflows for how DocuBoT and PREVENTION integrate with AVAROS, with clear examples and real-world scenarios.

### 7.1 DocuBoT Workflow (Document-Grounded Answers)

**Purpose:** Provide answers grounded in your organization's actual documents (procedures, manuals, specifications) rather than generic AI responses.

#### Document Lifecycle

(Three-stage document management process: UPLOAD documents via REST API, INDEXING by DocuBoT Service for extraction/chunking/embedding, READY in Vector Database for queries)

#### Query Workflow: Step-by-Step

**Scenario 1: Procedural Question**

**User asks:** "What's the maximum changeover time for injection molding Line 1?"

(Five-step workflow:
1. Intent Recognition: AVAROS detects procedural question and routes to DocuBoT
2. DocuBoT Query: AVAROS sends question with context including user role, asset, and department
3. DocuBoT Processing: Embeds question, searches vector database, retrieves top 3 relevant chunks with scores
4. DocuBoT Response: Returns answer with sources including document names, pages, sections, and confidence scores
5. AVAROS Response Formatting: Speaks formatted answer with source citations)

**Scenario 2: "Why" Question (Root Cause)**

**User asks:** "Why does Supplier B have higher defect rates than Supplier A?"

(Four-step integrated query process combining data and documentation:
1. Query Analysis: Identifies causal question type, extracts entities, determines strategy
2. Dual Query: Parallel execution querying RENERYOAdapter for defect rate data and DocuBoT for quality documentation
3. DocuBoT Finds Root Cause: Retrieves relevant quality report identifying moisture control issues
4. Integrated Response: AVAROS combines numerical data with documented root cause analysis)

**Scenario 3: Specification Lookup**

**User asks:** "What's the acceptable CO₂ emission range for our plastic molding process?"

(Four-step specification query:
1. Specification Query: AVAROS identifies environmental specification lookup
2. DocuBoT Search: Queries for emission standards, finds relevant section with confidence 0.95
3. Response with Current Status: Optionally queries current performance from RENERYO and compares to specification range
4. Complete Answer: Provides specification range and current compliance status with source citation)

#### DocuBoT Error Handling

**Case 1: No Relevant Documents Found**
When confidence is below 0.7, inform user that documentation is not available and suggest consulting supervisor or quality department.

**Case 2: Multiple Conflicting Sources**
When multiple sources found with conflicting information, acknowledge the conflict, cite the most recent document, and recommend verification with quality control.

**Case 3: Outdated Document**
When document age exceeds 365 days, provide answer but note the document date and age, recommending verification of currency.

---

### 7.2 PREVENTION Workflow (Anomaly Detection)

**Purpose:** Continuously monitor data streams and proactively alert users to unusual patterns, trend drift, and potential issues before they become critical.

#### PREVENTION Architecture

(Architecture diagram showing PREVENTION Service with three components: Data Ingestion (time series, real-time, batch) → Anomaly Detection (statistical and ML models) → Alert Generation (severity and context). Data flows from RENERYO Platform to Data Ingestion, and alerts sent via Webhook to AVAROS.)

#### Detection Methods

**1. Statistical Anomaly Detection (Z-Score)**

(PREVENTION internal logic using Z-score method: calculates mean and standard deviation of historical values, computes Z-score for current value, classifies severity as CRITICAL if abs(z-score) > 3.0, WARNING if > 2.0, INFO if > 1.0, returns anomaly status with deviation percentage)

**2. Trend Drift Detection**

(Visualization showing normal trend vs drift detected for Energy per Unit metric. Detection method: calculates 7-day moving average slope, triggers drift alert if slope changes by >15% from historical norm, provides context about daily increase rate and duration.)

#### Interactive Mode: User Asks AVAROS

**Scenario 1: General Anomaly Check**

**User asks:** "Any problems today?"

(Five-step anomaly detection workflow:
1. Intent Recognition: Identifies anomaly check intent for today with all metrics
2. AVAROS → PREVENTION Query: POST request to check endpoint with time range and min severity WARNING
3. PREVENTION Analysis: Checks 72 data points across energy, material, and supplier metrics
4. PREVENTION Finds Anomaly: Returns detection of energy spike on Line 2 during changeover with 15% deviation and context
5. AVAROS Response: Formats and speaks alert with metric, severity, context, and recommendation)

**Scenario 2: Specific Metric Check**

**User asks:** "Any issues with Line 3's scrap rate this week?"

(Three-step targeted query:
1. Targeted Query: POST request for specific metric, asset, and week time range with daily granularity
2. PREVENTION Detects Trend: Returns gradual increase trend showing 33% rise from 2.1% baseline to 2.8% current average over 7 days with daily values
3. AVAROS Response: Reports trend with percentage increase, baseline comparison, and recommendations for tool wear, material quality, or training investigation)

#### Proactive Mode: PREVENTION Interrupts AVAROS

**Scenario 3: Critical Anomaly Alert (Webhook)**

(Six-step proactive alert workflow:
1. PREVENTION Detects Critical Issue: CO₂ per unit 3.2 vs expected 2.4, Z-score 4.2, +3% per day for 5 days
2. PREVENTION Generates Alert: Creates alert with severity CRITICAL, deviation details, trend analysis, possible causes, and recommended actions
3. PREVENTION → AVAROS Webhook: POST to webhook endpoint with signed alert payload
4. AVAROS Receives Webhook: Processes alert, interrupts for CRITICAL or queues for WARNING
5. User Hears Proactive Alert: AVAROS interrupts with urgent message detailing the issue, possible causes, and recommended actions
6. User Can Ask Follow-Up: User can request trend details, AVAROS shows daily values and offers to create maintenance ticket)

**Scenario 4: Multi-Metric Correlation**

(PREVENTION detects correlated pattern across multiple metrics:
- Anomaly 1: Energy per unit ↑ 12% (Line 2)
- Anomaly 2: Cycle time ↑ 8% (Line 2)
- Anomaly 3: Scrap rate ↑ 15% (Line 2)

Correlation Analysis shows all three metrics affected on same asset, started same day, temporal correlation 0.94 (high), suggesting single equipment issue as likely root cause, possibly hydraulic system degradation or heater element failure. PREVENTION Alert recommends immediate Line 2 inspection.)

#### PREVENTION Configuration

**Threshold Customization via Web UI:**

(Users can configure thresholds for each metric via settings including:
- Warning and critical thresholds (sigma values)
- Notification timing (immediate or daily summary)
- Alert channels (voice AVAROS interrupt, email, SMS for critical escalation)

Example: energy_per_unit uses 2.0 sigma warning and 3.0 sigma critical with immediate notification; co2_per_unit uses more strict 2.5 critical threshold for compliance with multi-channel alerts)

**False Positive Feedback Loop:**

(Interactive learning process:
- User reports alert as false positive (e.g., "That was planned maintenance. Ignore.")
- AVAROS logs user feedback with alert ID, feedback type, and reason
- Sends feedback to PREVENTION for model improvement
- PREVENTION learns to check maintenance schedule before alerting
- Next time: PREVENTION avoids alerting for similar planned events)

---

### 7.3 Combined Workflow: Data + Documents + Anomalies

**Scenario: Complete Investigation**

**User asks:** "Why is Line 2's energy consumption high?"

(Two-step multi-source integration:
1. Multi-Source Query: AVAROS executes in parallel across three threads - RENERYO for current energy data, PREVENTION for anomaly detection, DocuBoT for maintenance logs and equipment manuals
2. AVAROS Synthesizes: Combines all sources into comprehensive answer explaining current consumption (15.2 kWh/unit, 18% above baseline), anomaly detection (started 3 days ago), root cause from maintenance log (hydraulic pump replaced), context from equipment manual (48-hour break-in period with 10-15% higher consumption), and prognosis (expected behavior, should return to normal within 24 hours))

**Key Integration Points:**

1. **Data (RENERYO)** provides: Current values, trends, comparisons
2. **Anomaly (PREVENTION)** provides: Deviation detection, severity, pattern recognition
3. **Knowledge (DocuBoT)** provides: Root causes, procedures, specifications
4. **AVAROS** provides: Natural language synthesis, decision support

This creates a complete answer: "What's happening" (data) + "Is it abnormal" (anomaly) + "Why" (knowledge) + "What to do" (recommendation).

---

*This implementation plan demonstrates complete understanding of the AVAROS project architecture, work packages, and development roadmap as specified in the WASABI 2 Open Call proposal.*
