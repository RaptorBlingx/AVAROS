# AVAROS Architecture & Implementation Workflow

> **AI-Voice-Assistant-Driven Resource-Optimized Sustainable Manufacturing**

This document describes the complete system architecture, component interactions, and implementation workflow for AVAROS. It serves as the technical blueprint for development.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architectural Principles](#2-architectural-principles)
3. [Layer Architecture](#3-layer-architecture)
4. [Component Specifications](#4-component-specifications)
5. [Data Flow & Communication](#5-data-flow--communication)
6. [The Five Query Types](#6-the-five-query-types)
7. [Canonical Data Model](#7-canonical-data-model)
8. [Platform Adapters](#8-platform-adapters)
9. [DocuBoT Integration](#9-docubot-integration)
10. [PREVENTION Integration](#10-prevention-integration)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Implementation Phases](#12-implementation-phases)

---

## 1. System Overview

AVAROS is a conversational AI assistant for manufacturing environments built on OVOS (Open Voice OS). It provides voice and text access to supply chain, energy, material, and carbon KPIs through a platform-agnostic architecture.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **KPI Retrieval** | Query real-time manufacturing metrics via natural language |
| **Comparison Analysis** | Compare suppliers, assets, or time periods side-by-side |
| **Trend Analysis** | Visualize and interpret metric trends over time |
| **Anomaly Detection** | Surface unusual patterns via PREVENTION integration |
| **What-If Simulation** | Predict outcomes of hypothetical changes |
| **Document Grounding** | Ground answers in procedures and specs via DocuBoT |

### Target KPIs (WASABI Proposal)

| Metric | Target Improvement |
|--------|-------------------|
| Electricity per unit | ≥8% reduction |
| Material efficiency | ≥5% improvement |
| CO₂-eq emissions | ≥10% reduction |

---

## 2. Architectural Principles

### 2.1 The Golden Rule

> **AVAROS understands "manufacturing concepts"**
> **Adapters understand "platform-specific APIs"**

Intent handlers work with universal manufacturing concepts (energy per unit, scrap rate, supplier lead time). They never reference specific platform APIs like RENERYO endpoints. Adapters translate between canonical concepts and platform-specific implementations.

### 2.2 Zero-Configuration Deployment

> **Clone → Docker Compose Up → Working System**

Users should never edit configuration files to run AVAROS. The system starts with a MockAdapter that provides realistic demo data out-of-the-box. Platform configuration happens via Web UI or Settings API after deployment.

### 2.3 Clean Architecture

AVAROS follows Clean Architecture with strict dependency rules:

- **Domain layer** has zero external dependencies
- **Use Cases** depend only on Domain
- **Adapters** depend on Use Cases and Domain
- **Infrastructure** depends on everything above

Inner layers never import from outer layers.

### 2.4 Platform Agnosticism

RENERYO is the first data provider, but AVAROS must work with any manufacturing platform (ISO 50001-compliant EnMS, generic MES/ERP systems, custom platforms). Adding a new platform means implementing a new adapter—no changes to skill handlers or domain logic.

---

## 3. Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│                    (OVOS Skill)                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Intent Handlers │ Dialog Manager │ Response Builder    │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                    USE CASE LAYER                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Query Dispatcher │ Audit Logger │ Settings Service     │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                    ADAPTER LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ MockAdapter │  │ RENERYO     │  │ Future Adapters         │ │
│  │ (demo)      │  │ Adapter     │  │ (GenericEnMS, custom)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                    DOMAIN LAYER                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Canonical Metrics │ Result Types │ Time Period │ Errors │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Owns | Does NOT Own |
|-------|------|--------------|
| **Presentation** | Intent recognition, slot extraction, dialog formatting | Data fetching, business logic |
| **Use Case** | Orchestration, routing, auditing, caching | Platform API calls, UI concerns |
| **Adapter** | Platform API calls, authentication, response mapping | Business logic, dialog phrasing |
| **Domain** | Data structures, validation rules, metric definitions | I/O, persistence, external calls |

---

## 4. Component Specifications

### 4.1 OVOS Skill (AVAROS Skill)

The OVOS Skill is the entry point for all user interactions.

**Responsibilities:**
- Register intents for the five query types
- Extract slots (metric name, time period, asset, supplier)
- Invoke QueryDispatcher with canonical parameters
- Format results for voice output (under 30 words)
- Handle errors gracefully with user-friendly dialogs

**Intent Organization:**
- Intent files follow pattern: `{query_type}.{domain}.{detail}.intent`
- Dialog files follow pattern: `{query_type}.{domain}.dialog`
- Vocabulary files define synonyms and aliases

### 4.2 Query Dispatcher

The QueryDispatcher is the central orchestration component.

**Responsibilities:**
- Route queries to the correct adapter method based on query type
- Provide synchronous wrapper around async adapter methods (OVOS compatibility)
- Create audit log entries for every query
- Handle adapter exceptions with appropriate error responses
- Support future caching layer insertion

**Query Routing Table:**

| Query Type | Dispatcher Method | Adapter Method Called |
|------------|-------------------|----------------------|
| GET_KPI | dispatch_kpi() | adapter.get_kpi() |
| COMPARE | dispatch_compare() | adapter.compare() |
| GET_TREND | dispatch_trend() | adapter.get_trend() |
| CHECK_ANOMALY | dispatch_anomaly() | adapter.check_anomaly() |
| SIMULATE_WHATIF | dispatch_whatif() | adapter.simulate_whatif() |

### 4.3 Adapter Factory

The AdapterFactory manages adapter lifecycle and selection.

**Responsibilities:**
- Maintain registry of available adapter implementations
- Instantiate adapters based on current configuration
- Support hot-reload when configuration changes (no restart required)
- Default to MockAdapter when no platform is configured

**Adapter Selection Logic:**
1. Read platform type from SettingsService
2. Look up adapter class in registry
3. Instantiate with platform-specific configuration
4. Return adapter instance to QueryDispatcher

### 4.4 Settings Service

The SettingsService provides runtime configuration via database.

**Responsibilities:**
- Store platform credentials securely (encrypted at rest)
- Provide CRUD operations for configuration
- Signal adapter reload on configuration change
- Support first-run wizard flow

**Configuration Categories:**
- Platform connection (type, URL, API key)
- Alert thresholds
- User preferences
- Feature flags

### 4.5 Audit Logger

The AuditLogger provides GDPR-compliant query logging.

**Responsibilities:**
- Create immutable audit records for every query
- Store query metadata without personal identifiers
- Track recommendation IDs for traceability
- Support retention policies (90 days operational, 1 year audit)

**Audit Record Fields:**
- Timestamp (UTC)
- Query ID (unique identifier)
- User role (NOT personal identifier)
- Intent name
- Data sources accessed
- Recommendation ID (if applicable)
- Response summary

### 4.6 Response Builder

The ResponseBuilder formats results for voice output.

**Responsibilities:**
- Convert result objects to natural language
- Respect voice constraints (under 30 words for primary response)
- Support verbosity levels (brief, normal, detailed)
- Include confidence and evidence references
- Format numbers appropriately (rounding, units)

---

## 5. Data Flow & Communication

### 5.1 Query Lifecycle

**Step 1: User Utterance**
User speaks or types: "What's our energy per unit this week?"

**Step 2: Intent Recognition**
OVOS matches utterance to `kpi.energy.per_unit.intent` and extracts slots:
- metric: ENERGY_PER_UNIT
- period: this_week
- asset: (default/all)

**Step 3: Intent Handler**
The skill's intent handler receives the match and calls QueryDispatcher with:
- Query type: GET_KPI
- Metric: ENERGY_PER_UNIT
- Time period: This week (resolved to actual dates)

**Step 4: Query Dispatch**
QueryDispatcher:
1. Creates audit log entry
2. Gets adapter from AdapterFactory
3. Calls adapter.get_kpi() asynchronously
4. Waits for result
5. Updates audit log with outcome

**Step 5: Adapter Execution**
The active adapter (Mock or RENERYO):
1. Translates canonical metric to platform-specific query
2. Calls platform API (or generates mock data)
3. Maps response to KPIResult

**Step 6: Response Building**
ResponseBuilder converts KPIResult to speech:
- "Energy per unit this week is 12.3 kilowatt-hours, down 5% from last week."

**Step 7: Dialog Output**
OVOS speaks the response via text-to-speech.

### 5.2 Component Communication Matrix

| From | To | Method | Protocol |
|------|-----|--------|----------|
| OVOS | Intent Handler | Event callback | OVOS message bus |
| Intent Handler | QueryDispatcher | Sync method call | Python |
| QueryDispatcher | Adapter | Async method call | Python asyncio |
| QueryDispatcher | AuditLogger | Sync method call | Python |
| AdapterFactory | SettingsService | Sync method call | Python |
| RENERYOAdapter | RENERYO API | HTTP request | REST/JSON over TLS |
| AVAROS Skill | DocuBoT | HTTP request | REST/JSON |
| AVAROS Skill | PREVENTION | HTTP request | REST/JSON |
| PREVENTION | AVAROS Skill | HTTP webhook | REST/JSON |

---

## 6. The Five Query Types

AVAROS supports exactly five query types. Every user intent maps to one of these patterns.

### 6.1 KPI Retrieval (GET_KPI)

**Purpose:** Retrieve a single metric value for a given scope and time period.

**Input Parameters:**
- metric: CanonicalMetric enum value
- period: TimePeriod (start date, end date)
- asset_id: Optional asset filter
- supplier_id: Optional supplier filter

**Output:** KPIResult containing:
- Metric name and value
- Unit of measurement
- Comparison to previous period (delta)
- Confidence level
- Data timestamp

**Example Utterances:**
- "What's our OEE today?"
- "Show me the scrap rate for Line 1"
- "Energy per unit last month"

### 6.2 Comparison (COMPARE)

**Purpose:** Compare multiple entities (suppliers, assets, periods) on one or more metrics.

**Input Parameters:**
- metric: CanonicalMetric to compare
- entities: List of entity IDs to compare
- entity_type: SUPPLIER, ASSET, or PERIOD
- period: Time period for comparison

**Output:** CompareResult containing:
- Ranked list of entities with values
- Winner identification
- Percentage differences
- Statistical significance indicator

**Example Utterances:**
- "Compare Supplier A versus Supplier B on defect rate"
- "Which production line has the best OEE?"
- "Compare this month to last month on energy"

### 6.3 Trend Analysis (GET_TREND)

**Purpose:** Retrieve time-series data for a metric and analyze direction.

**Input Parameters:**
- metric: CanonicalMetric to trend
- period: TimePeriod covering trend window
- granularity: HOURLY, DAILY, WEEKLY, MONTHLY
- asset_id: Optional asset filter

**Output:** TrendResult containing:
- List of DataPoint (timestamp, value) pairs
- Trend direction: IMPROVING, DECLINING, STABLE
- Slope and statistical confidence
- Forecast for next period (optional)

**Example Utterances:**
- "Show energy trend for the last 3 months"
- "Is our scrap rate improving?"
- "CO2 emissions trend weekly"

### 6.4 Anomaly Detection (CHECK_ANOMALY)

**Purpose:** Identify unusual patterns or outliers in metrics.

**Input Parameters:**
- metric: Optional specific metric to check
- asset_id: Optional asset to check
- period: Time window for analysis
- severity_threshold: Minimum severity to report

**Output:** AnomalyResult containing:
- List of detected anomalies
- Each anomaly has: metric, timestamp, value, expected value, severity, description
- Severity levels: INFO, WARNING, CRITICAL
- Recommended actions

**Example Utterances:**
- "Any unusual patterns today?"
- "Check for anomalies on Line 2"
- "Are there any energy spikes?"

### 6.5 What-If Simulation (SIMULATE_WHATIF)

**Purpose:** Predict impact of hypothetical changes.

**Input Parameters:**
- scenario_type: MATERIAL_CHANGE, SUPPLIER_CHANGE, SCHEDULE_CHANGE, PARAMETER_CHANGE
- changes: Dictionary of parameter modifications
- baseline_period: Period to use as baseline
- target_metrics: Metrics to predict

**Output:** WhatIfResult containing:
- Predicted values for target metrics
- Delta from baseline
- Confidence intervals
- Assumptions made
- Caveats and limitations

**Example Utterances:**
- "What if we switch to recycled plastic?"
- "If we change to Supplier B, what happens to lead time?"
- "Simulate running third shift"

---

## 7. Canonical Data Model

### 7.1 Canonical Metrics

AVAROS defines a fixed set of manufacturing metrics. All platforms translate their data to these canonical forms.

**Energy Metrics:**
| Metric | Unit | Description |
|--------|------|-------------|
| ENERGY_PER_UNIT | kWh | Electricity consumed per produced unit |
| ENERGY_TOTAL | kWh | Total energy consumption |
| PEAK_DEMAND | kW | Maximum power draw |
| PEAK_TARIFF_EXPOSURE | % | Time in peak tariff periods |

**Material Metrics:**
| Metric | Unit | Description |
|--------|------|-------------|
| SCRAP_RATE | % | Percentage of material scrapped |
| REWORK_RATE | % | Percentage requiring rework |
| MATERIAL_EFFICIENCY | % | Usable output vs input ratio |
| RECYCLED_CONTENT | % | Recycled material percentage |

**Supplier Metrics:**
| Metric | Unit | Description |
|--------|------|-------------|
| SUPPLIER_LEAD_TIME | days | Average delivery lead time |
| SUPPLIER_DEFECT_RATE | % | Incoming defect rate |
| SUPPLIER_ON_TIME | % | On-time delivery rate |
| SUPPLIER_CO2_PER_KG | kg CO₂/kg | Carbon intensity of supply |

**Production Metrics:**
| Metric | Unit | Description |
|--------|------|-------------|
| OEE | % | Overall Equipment Effectiveness |
| THROUGHPUT | units/hr | Production rate |
| CYCLE_TIME | seconds | Time per unit |
| CHANGEOVER_TIME | minutes | Setup time between products |

**Carbon Metrics:**
| Metric | Unit | Description |
|--------|------|-------------|
| CO2_PER_UNIT | kg CO₂-eq | Carbon per produced unit |
| CO2_TOTAL | tonnes CO₂-eq | Total carbon emissions |
| CO2_PER_BATCH | kg CO₂-eq | Carbon per production batch |

### 7.2 Time Period Model

Time periods are immutable value objects with factory methods:

**Factory Methods:**
- today() — Current day
- yesterday() — Previous day
- this_week() — Current calendar week
- last_week() — Previous calendar week
- this_month() — Current calendar month
- last_month() — Previous calendar month
- last_n_days(n) — Rolling window
- custom(start, end) — Explicit date range

### 7.3 Result Types

All adapter methods return frozen (immutable) result objects:

**KPIResult:** Single metric value with metadata
**CompareResult:** Ranked entity comparison
**TrendResult:** Time series with direction analysis
**AnomalyResult:** Detected anomalies with severity
**WhatIfResult:** Simulation predictions with confidence

Each result type includes:
- query_id: Unique identifier for audit trail
- timestamp: When result was generated
- data_freshness: Age of underlying data
- confidence: Reliability indicator

### 7.4 Error Hierarchy

AVAROS defines a structured exception hierarchy:

**AVAROSError** (base)
├── **AdapterError** — Platform communication failures
│   ├── ConnectionError — Cannot reach platform
│   ├── AuthenticationError — Invalid credentials
│   └── TimeoutError — Request timed out
├── **ValidationError** — Invalid input parameters
│   ├── MetricNotFoundError — Unknown metric requested
│   └── PeriodInvalidError — Invalid date range
└── **ConfigurationError** — System misconfiguration

---

## 8. Platform Adapters

### 8.1 ManufacturingAdapter Interface

All platform adapters implement the ManufacturingAdapter abstract base class.

**Required Methods:**

| Method | Parameters | Returns | Purpose |
|--------|------------|---------|---------|
| get_kpi | metric, period, asset_id, supplier_id | KPIResult | Retrieve single KPI |
| compare | metric, entities, entity_type, period | CompareResult | Compare entities |
| get_trend | metric, period, granularity, asset_id | TrendResult | Time series analysis |
| check_anomaly | metric, asset_id, period, threshold | AnomalyResult | Anomaly detection |
| simulate_whatif | scenario_type, changes, baseline, targets | WhatIfResult | Predictive simulation |

**Capability Discovery:**
Each adapter declares which features it supports:
- supports_whatif: Boolean
- supports_anomaly: Boolean
- supported_metrics: List of CanonicalMetric
- max_trend_granularity: Finest time granularity available

### 8.2 MockAdapter

The MockAdapter provides zero-configuration demo capability.

**Characteristics:**
- Requires no external API or credentials
- Generates realistic, consistent mock data
- Supports all five query types
- Uses seeded randomization for reproducibility
- Simulates realistic latency patterns

**Data Generation:**
- Maintains internal "mock factory" state
- KPIs follow realistic distributions per industry
- Trends include seasonality patterns
- Anomalies injected at configurable rate
- What-if uses simple heuristic models

### 8.3 RENERYOAdapter

The RENERYOAdapter connects AVAROS to ArtiBilim's RENERYO platform.

**Configuration Required:**
- API base URL
- API key (stored encrypted)
- Organization/tenant ID
- Polling interval for live data

**Metric Mapping:**
Each canonical metric maps to specific RENERYO API endpoints and field names. This mapping is defined in configuration, not hardcoded.

**Authentication:**
- Bearer token via API key
- Token refresh handled automatically
- Graceful degradation on auth failure

**Error Handling:**
- Retries with exponential backoff
- Circuit breaker for repeated failures
- Fallback to cached values when appropriate

### 8.4 Future Adapters

The architecture supports additional adapters without core changes:

**Potential Adapters:**
- GenericEnMSAdapter — ISO 50001-compliant EnMS platforms
- CustomMESAdapter — Generic MES/ERP connector
- OPCUAAdapter — OPC-UA industrial protocol connector
- CSVAdapter — File-based data import
- MQTTAdapter — MQTT sensor data ingestion

**Adding a New Adapter:**
1. Implement ManufacturingAdapter interface
2. Define metric mapping configuration
3. Register adapter class in AdapterFactory
4. Add platform type to SettingsService options

---

## 9. DocuBoT Integration

DocuBoT provides Retrieval-Augmented Generation (RAG) for document-grounded answers.

### 9.1 Purpose

When users ask questions that require procedural knowledge, specifications, or regulatory context, DocuBoT retrieves relevant document passages and grounds the response in authoritative sources.

### 9.2 Document Corpus

**Indexed Documents:**
- Standard Operating Procedures (SOPs)
- Technical specifications
- Supplier declarations and certifications
- LCA (Life Cycle Assessment) factors
- Emission factor tables
- Equipment manuals
- Quality standards

### 9.3 Integration Flow

**Step 1: Query Classification**
The intent handler determines if the query requires document grounding (procedural questions, "why" questions, specification lookups).

**Step 2: DocuBoT Query**
AVAROS sends the user query to DocuBoT service via REST API.

**Step 3: Retrieval**
DocuBoT:
1. Embeds query using language model
2. Searches vector store for similar passages
3. Retrieves top-k relevant chunks
4. Ranks by relevance score

**Step 4: Grounded Response**
DocuBoT returns:
- Generated answer
- Source citations (document, page, section)
- Confidence score
- Retrieved passage excerpts

**Step 5: Response Formatting**
AVAROS presents the answer with citations:
"According to SOP-2023-045, the maximum changeover time should be 15 minutes. Source: Quality Manual, Section 4.2."

### 9.4 Configuration

**DocuBoT Settings:**
- Service URL
- Index name/collection
- Top-k retrieval count
- Minimum confidence threshold
- Language preference

---

## 10. PREVENTION Integration

PREVENTION provides anomaly and drift detection services.

### 10.1 Purpose

PREVENTION monitors time-series data streams and detects statistical anomalies, trend shifts, and early warning signals that merit operator attention.

### 10.2 Detection Methods

**Statistical Methods:**
- Z-score analysis (sigma bands)
- Moving average deviations
- Seasonal decomposition

**Alert Severity Levels:**
| Level | Threshold | Action |
|-------|-----------|--------|
| INFO | 1-2σ | Log only, no notification |
| WARNING | 2-3σ | Notify user when relevant |
| CRITICAL | >3σ | Urgent interrupt, immediate notification |

### 10.3 Integration Patterns

**Pattern A: On-Demand Check**
User asks "Any anomalies today?" → AVAROS queries PREVENTION → Returns AnomalyResult

**Pattern B: Proactive Alerts**
PREVENTION detects anomaly → Sends webhook to AVAROS → AVAROS notifies user proactively

### 10.4 Data Flow for Proactive Alerts

**Step 1: Data Ingestion**
PREVENTION receives time-series data from platform (via RENERYO or direct sensor feeds).

**Step 2: Analysis**
PREVENTION runs detection algorithms continuously or on schedule.

**Step 3: Alert Generation**
When anomaly exceeds threshold, PREVENTION creates alert payload:
- Metric affected
- Current value vs expected
- Severity level
- Timestamp
- Recommended action

**Step 4: Webhook Delivery**
PREVENTION POSTs alert to AVAROS webhook endpoint.

**Step 5: User Notification**
AVAROS interrupts current conversation (if CRITICAL) or queues notification (if WARNING) to inform user.

### 10.5 Configuration

**PREVENTION Settings:**
- Service URL
- Webhook endpoint for callbacks
- Alert threshold overrides per metric
- Notification preferences (immediate, batched, silent)

---

## 11. Deployment Architecture

### 11.1 Docker-Compose Stack

AVAROS deploys as a containerized stack orchestrated by Docker-Compose.

**Services:**

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| avaros-skill | avaros/skill | OVOS skill container | — |
| ovos-core | ovos/core | Voice assistant core | 8080 |
| docubot | wasabi/docubot | RAG service | 8081 |
| prevention | wasabi/prevention | Anomaly detection | 8082 |
| postgres | postgres:15 | Settings & audit database | 5432 |
| redis | redis:7 | Caching layer | 6379 |

### 11.2 Volume Mounts

| Volume | Purpose |
|--------|---------|
| avaros-data | SQLite/PostgreSQL data files |
| avaros-logs | Application and audit logs |
| docubot-index | Vector store indices |
| ovos-config | OVOS configuration |

### 11.3 Network Architecture

All services communicate on internal Docker network. Only necessary ports exposed to host:
- 8080: Web UI / API gateway
- 1880: OVOS messagebus (optional debug)

External platform APIs accessed via outbound HTTPS.

### 11.4 Security Controls

| Control | Implementation |
|---------|----------------|
| TLS | All external API calls use TLS 1.2+ |
| Secrets | Environment variables, Docker secrets |
| RBAC | Role-based access via SettingsService |
| Audit | Immutable logs with retention policies |
| Encryption | Credentials encrypted at rest (Fernet) |

---

## 12. Implementation Phases

### Phase 1: Foundation (Weeks 1-4)

**Objectives:**
- Establish domain model and core abstractions
- Implement MockAdapter for demo capability
- Create basic OVOS skill with intent handlers
- Set up Docker-Compose development environment

**Deliverables:**
- Domain models (metrics, results, errors)
- ManufacturingAdapter interface
- MockAdapter implementation
- QueryDispatcher with routing logic
- Basic intents for all five query types
- Docker-Compose for local development

### Phase 2: Services & Quality (Weeks 5-8)

**Objectives:**
- Implement SettingsService with database backend
- Add AuditLogger for compliance
- Create ResponseBuilder for voice output
- Achieve test coverage targets
- Complete English locale files

**Deliverables:**
- SettingsService with encrypted credential storage
- AuditLogger with GDPR compliance
- ResponseBuilder with verbosity levels
- Unit and integration test suites
- Complete intent and dialog files

### Phase 3: Platform Integration (Weeks 9-14)

**Objectives:**
- Implement RENERYOAdapter
- Integrate DocuBoT service
- Integrate PREVENTION service
- Validate on ArtiBilim testbed

**Deliverables:**
- RENERYOAdapter with full metric mapping
- DocuBoT client and grounding flows
- PREVENTION client and webhook handler
- Testbed validation report

### Phase 4: Deployment & Polish (Weeks 15-18)

**Objectives:**
- Production Docker-Compose configuration
- Web UI for configuration
- Performance optimization
- Security hardening
- Documentation completion

**Deliverables:**
- Production-ready Docker images
- Configuration Web UI
- Performance benchmarks
- Security audit report
- Complete documentation package

### Phase 5: Pilot & Publication (Weeks 19-24)

**Objectives:**
- Deploy to pilot sites
- Measure KPI improvements
- Package for WASABI Shop
- Create replication assets

**Deliverables:**
- Pilot deployment at designated factory
- KPI measurement report
- WASABI Shop listing
- Installation checklist and getting-started guide
- Anonymized resource-efficiency analysis

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Adapter** | Component that translates between AVAROS canonical model and platform-specific APIs |
| **Canonical Metric** | Standardized manufacturing metric independent of data source |
| **DocuBoT** | WASABI RAG service for document-grounded answers |
| **Intent** | User's expressed goal, recognized by OVOS from speech/text |
| **OVOS** | Open Voice OS, the voice assistant framework |
| **PREVENTION** | WASABI anomaly detection service |
| **Query Type** | One of five interaction patterns (KPI, Compare, Trend, Anomaly, What-If) |
| **RENERYO** | ArtiBilim's supply-chain optimization platform |
| **Slot** | Parameter extracted from user utterance (metric name, date, etc.) |

---

## Appendix B: Reference Documents

- WASABI 2nd Call Proposal (AVAROS)
- OVOS Documentation: https://openvoiceos.github.io/ovos-technical-manual/
- DocuBoT Integration Guide (WASABI)
- PREVENTION API Specification (WASABI)
- RENERYO API Documentation (ArtiBilim)

---

*Document Version: 1.0*
*Last Updated: February 2026*
*Status: Planning Phase*
