# AVAROS Architecture & Implementation Workflow

**Document Status:** Planning & Design  
**Last Updated:** February 4, 2026  
**Project Phase:** Pre-Implementation  
**Alignment:** WASABI 2 Open Call Proposal

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architectural Vision](#architectural-vision)
3. [Core Design Principles](#core-design-principles)
4. [System Architecture](#system-architecture)
5. [Component Specifications](#component-specifications)
6. [Zero-Config Web UI](#zero-config-web-ui)
7. [Data Flow & Communication](#data-flow--communication)
8. [Transport Layer Architecture](#transport-layer-architecture)
9. [Implementation Phases](#implementation-phases)
10. [Integration Strategy](#integration-strategy)
11. [Security & Compliance](#security--compliance)
12. [Deployment Architecture](#deployment-architecture)
13. [KPI Targets & Validation](#kpi-targets--validation)

---

## Executive Summary

AVAROS (AI-Voice-Assistant-Driven Resource-Optimized Sustainable Manufacturing) is a generic operational intelligence assistant designed for industrial and operational environments. The system provides conversational access to system metrics, device status, and operational data through an OVOS-based voice interface, enabling operators, engineers, and planners to make faster, data-driven decisions across diverse backend platforms.

### Project Objectives

- Enable natural-language queries for operational data (device status, system metrics, performance trends, maintenance information)
- Provide generic skills applicable across different solutions: device control, status queries, trend visualization, documentation access, edge device management
- Deliver a platform-agnostic framework that works with ANY backend system (manufacturing platforms, building management, IoT systems, etc.)
- Create a portable, reusable assistant package for WASABI White-Label Shop adoption by other SMEs
- Maintain GDPR compliance, EU AI Act alignment, and ISO/IEC 27001-aligned security from day one

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Voice Interface | OVOS (Open Voice OS) | Intent recognition, dialogue management, TTS/STT |
| Configuration UI | FastAPI + React | Zero-config web-based platform setup and metric mapping |
| Document Grounding | DocuBoT | RAG retrieval for solution documentation, user guides, procedures |
| Anomaly Detection | PREVENTION | Statistical anomaly detection and drift monitoring |
| Data Ingestion | Custom Service (Python) | MQTT/OPC-UA subscriber with time-series buffer |
| Backend Platform | Platform-agnostic (adapters for any system) | Extensible adapter pattern for RENERYO, SAP, building management, IoT platforms, etc. |
| Deployment | Docker-Compose | Portable, repeatable, zero-config deployment |

---

## Architectural Vision

### Golden Rule

> **"AVAROS understands generic operational concepts; Adapters understand platform-specific APIs"**

This principle ensures:
- AVAROS skill code never references specific backend platforms (RENERYO, SAP, building management systems, IoT platforms)
- All platform-specific logic is encapsulated in adapter implementations
- New platforms can be integrated by implementing the adapter interface without modifying skill logic
- The system remains vendor-neutral and portable across different operational data sources

### Zero-Config Philosophy

> **"Clone → Docker Compose Up → Working System"**

Users should never edit code files or YAML configurations to run AVAROS. The system implements:

**Zero-Touch Deployment:**
- Start with MockAdapter for immediate demo capability (no platform required)
- Access Web UI at `http://localhost:8080` for first-run wizard
- All configuration via browser forms (no file editing)
- Pre-built templates for RENERYO and generic REST platforms
- Store all settings in encrypted database (not configuration files)
- Support hot-reload when configuration changes without container restarts

**Transport-Agnostic Integration (Per WASABI Proposal):**
- **REST/JSON**: Configure base URL, endpoints, authentication, JSONPath mappings
- **MQTT**: Configure broker, topics, QoS; data flows to time-series buffer
- **OPC-UA**: Configure server URL, node IDs, security policy
- **CSV/Parquet**: Configure file paths, refresh schedules, schema mappings

This fulfills the proposal commitment: *"another SME will be able to point the assistant to its own sources with limited adaptation."* The Web UI **IS** that "limited adaptation" mechanism.

---

## Core Design Principles

### 1. Platform-Agnostic Design (DEC-001)

AVAROS must work with ANY backend platform, not just RENERYO. The Adapter Pattern ensures:
- **Intent handlers** operate on universal operational concepts
- **Query Dispatcher** routes requests to the appropriate adapter method
- **Platform Adapter Interface** defines the contract all platforms must implement
- **Universal Data Model** standardizes all responses regardless of source platform

### 2. Two-Layer Architecture: Generic Framework + Manufacturing Skill Pack (DEC-002)

**Reconciling Generic Infrastructure with Proposal Commitments:**

AVAROS implements a **two-layer design** that satisfies both reusability (generic infrastructure) and WASABI commitments (manufacturing KPIs):

```
┌─────────────────────────────────────────────────────────────────┐
│  WASABI Deliverable: Manufacturing Skill Pack                   │
│  ├── Intents: kpi.energy.per_unit, compare.supplier, etc.      │
│  ├── Dialogs: Manufacturing-specific response templates         │
│  ├── Metric Mappings: energy_per_unit → generic get_metric()   │
│  └── KPI Targets: 8% electricity, 5% material, 10% CO₂         │
└────────────────────────────┬────────────────────────────────────┘
                             │ configures
┌────────────────────────────▼────────────────────────────────────┐
│  Generic Skill Framework (Reusable Infrastructure)              │
│  ├── Capabilities: status, trends, control, docs, device mgmt  │
│  ├── QueryDispatcher: routes by operation type                  │
│  ├── ResponseBuilder: formats results to speech                 │
│  └── AuditLogger: GDPR compliance                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls
┌────────────────────────────▼────────────────────────────────────┐
│  Adapter Interface (Platform-Agnostic)                          │
│  └── Implemented by platform-specific adapters                  │
└──────────────────────────────────────────────────────────────────┘
```

**What Gets Published to WASABI Shop:**
- Manufacturing Skill Pack + Generic Framework (bundled as single deliverable)
- Pre-configured for manufacturing KPIs (energy, material, CO₂)
- Extensible: other domains can create their own Skill Packs using same framework

**Generic Skills Framework (Infrastructure Capabilities):**

The framework provides reusable capabilities that ANY Skill Pack can use:

| Skill Category | Purpose | User Examples | Orchestration |
|----------------|---------|---------------|---------------|
| **Device Control** | Turn on/off devices, start/stop systems | "Turn on device X", "Stop system Y" | Adapter → Response |
| **Status Queries** | Get current state, health, availability | "What's the status of device X?", "Is system Y online?" | Adapter → Response |
| **Trend Visualization** | Show performance over time | "Show trends", "How has system Y performed?" | Adapter → Response |
| **Documentation Access** | Retrieve solution docs, guides, help | "What does this solution do?", "How do I configure X?" | DocuBoT → Response |
| **Comparison** | Compare entities or time periods | "Compare System A vs B", "This month vs last" | Adapter → Response |
| **Anomaly Detection** | Identify unusual patterns | "Any unusual patterns?", "Detect issues on system X" | Adapter → PREVENTION → Response |
| **What-If Simulation** | Model scenario impacts | "What if I change parameter X?", "Impact of threshold change?" | Adapter → DocuBoT → Response |

**Manufacturing Skill Pack (WASABI Deliverable):**

The Manufacturing Skill Pack is the **primary deliverable** to the WASABI White-Label Shop. It configures the generic framework with:

| Component | Manufacturing-Specific Content |
|-----------|-------------------------------|
| **Intents** | `kpi.energy.per_unit.intent`, `compare.supplier.intent`, `trend.scrap.intent`, `anomaly.production.check.intent`, `whatif.temperature.intent` |
| **Dialogs** | *"Energy per unit for {asset} is {value} kWh, which is {percent}% {above/below} target"* |
| **Metric Vocabulary** | `energy_per_unit`, `scrap_rate`, `supplier_lead_time`, `co2_per_unit`, `oee`, `material_efficiency` |
| **KPI Targets** | 8% electricity reduction, 5% material efficiency, 10% CO₂ reduction (validation criteria) |
| **Documentation** | Manufacturing procedures, material specs, supplier contracts (DocuBoT corpus) |
| **Pre-Built Templates** | RENERYO adapter template with manufacturing endpoints pre-mapped |

**Extensibility for Other Domains:**

Other SMEs can create their own Skill Packs (e.g., Building Management, Logistics, Healthcare) by:
1. Defining domain-specific intents using the same patterns
2. Mapping their metrics to canonical vocabulary (or extending it)
3. Implementing/configuring an adapter for their platform
4. Indexing domain-specific documents in DocuBoT

The Generic Framework remains unchanged; only the Skill Pack changes.

---

### 3. Clean Architecture Layers (DEC-003)

The system follows strict layering to ensure maintainability and testability:

```
┌─────────────────────────────────────────────────────────────────┐
│  Presentation Layer (OVOS Skill)                                │
│  - Intent handlers                                               │
│  - Dialog templates                                              │
│  - Response formatting                                           │
└────────────────────────────┬────────────────────────────────────┘
                             │ depends on
┌────────────────────────────▼────────────────────────────────────┐
│  Use Case Layer                                                  │
│  - QueryDispatcher (orchestration)                               │
│  - ResponseBuilder (formatting)                                  │
│  - AuditLogger (compliance)                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ depends on
┌────────────────────────────▼────────────────────────────────────┐
│  Adapter Layer (Infrastructure)                                  │
│  - ManufacturingAdapter interface                                │
│  - MockAdapter, RENERYOAdapter, future adapters                  │
│  - AdapterFactory                                                │
└────────────────────────────┬────────────────────────────────────┘
                             │ uses
┌────────────────────────────▼────────────────────────────────────┐
│  Domain Layer (Pure Business Logic)                             │
│  - CanonicalMetric enum                                          │
│  - Immutable domain models (frozen dataclasses)                  │
│  - Result types (KPIResult, TrendResult, etc.)                   │
└──────────────────────────────────────────────────────────────────┘
```

**Dependency Rule:** Outer layers depend on inner layers, never the reverse.

### 4. Immutable Domain Models (DEC-004)

All domain objects will be implemented as frozen dataclasses:
- Prevents accidental mutation
- Thread-safe by design
- Hashable for caching
- Clear state management

### 5. Async-First with Sync Wrappers (DEC-005)

- Adapter methods are async for I/O efficiency
- QueryDispatcher provides sync wrappers for OVOS compatibility
- Background tasks handled via asyncio event loop

### 6. Intelligence Services Are Platform-Independent (DEC-007)

> **DocuBoT and PREVENTION are Use Case Layer services, NOT adapter extensions.**

This critical rule ensures:
- **Adapters only do data transformation** - fetch platform data → canonical format
- **Intelligence services (DocuBoT, PREVENTION) live in the orchestration layer** - they are called by QueryDispatcher, not by adapters
- **Future adapters don't re-implement intelligence** - a SAPAdapter or GenericEnMSAdapter gets the same DocuBoT grounding and PREVENTION anomaly detection automatically
- **Clear separation of concerns** - data access vs. decision support

**Wrong:**
```
QueryDispatcher → RENERYOAdapter → DocuBoT, PREVENTION
```

**Correct:**
```
QueryDispatcher → 
    ├── Adapter (data only)
    ├── DocuBoT (grounding)  
    └── PREVENTION (anomaly)
    → ResponseBuilder
```

---

## System Architecture

### High-Level Component Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                      User (Voice/Text Input)                      │
└───────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                    OVOS Framework (Core)                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              AVAROSSkill (Custom Skill)                     │  │
│  │  • Intent recognition & extraction                          │  │
│  │  • Slot filling & validation                                │  │
│  │  • Dialog management                                        │  │
│  └────────────────────────────┬────────────────────────────────┘  │
└────────────────────────────────┼───────────────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────────────┐
│                   Use Case Orchestration Layer                     │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ QueryDispatcher  │  │ ResponseBuilder  │  │  AuditLogger    │  │
│  │  (Orchestrator)  │  │  (Formatting)    │  │  (GDPR logs)    │  │
│  │  • Route queries │  │  • Voice-optimized│  │ • Immutable    │  │
│  │  • Coordinate    │  │  • Recommendations│  │ • Retention    │  │
│  │    services      │  │  • Citations     │  │                 │  │
│  └────────┬─────────┘  └──────────────────┘  └─────────────────┘  │
│           │                                                        │
│           ├─────────────────┬─────────────────┐                   │
│           ▼                 ▼                 ▼                   │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐      │
│  │ DocuBoT Client  │ │PREVENTION Client│ │ Adapter Call    │      │
│  │ (Grounding)     │ │(Anomaly Check)  │ │ (Data Fetch)    │      │
│  │ • What-if docs  │ │ • Drift detect  │ │ • KPI retrieval │      │
│  │ • Procedure ref │ │ • Alert scoring │ │ • Trend data    │      │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘      │
│           │                   │                   │               │
└───────────┼───────────────────┼───────────────────┼───────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│  DocuBoT Service  │ │PREVENTION Service │ │  Adapter Layer        │
│  (External)       │ │(External)         │ │                       │
│  • RAG retrieval  │ │ • Statistical     │ │  ┌─────────────────┐  │
│  • Document index │ │   process control │ │  │ManufacturingABC │  │
│  • Source links   │ │ • Isolation forest│ │  │ • get_kpi()     │  │
└───────────────────┘ └───────────────────┘ │  │ • compare()     │  │
                                            │  │ • get_trend()   │  │
                                            │  │ • get_raw_data()│  │
                                            │  └────────┬────────┘  │
                                            │           │           │
                                            │  ┌────────┴────────┐  │
                                            │  │                 │  │
                                            │  ▼                 ▼  │
                                            │┌──────────┐┌────────┐ │
                                            ││MockAdapt.││RENERYO │ │
                                            ││(Demo)    ││Adapter │ │
                                            │└──────────┘└───┬────┘ │
                                            └────────────────┼──────┘
                                                             │
                                                             ▼
                                            ┌────────────────────────┐
                                            │   RENERYO Platform     │
                                            │   (Data Source Only)   │
                                            │   • ERP/MES data       │
                                            │   • Supplier records   │
                                            │   • Batch tracking     │
                                            └────────────────────────┘
```

### Domain Layer: Universal Metric Framework

All platforms must map their proprietary metrics to the universal metric framework:

| Category | Generic Metrics |
|----------|----------------|
| **Device/System Status** | `status`, `health`, `availability`, `connectivity` |
| **Performance Metrics** | `throughput`, `response_time`, `success_rate`, `error_rate` |
| **Resource Utilization** | `cpu_usage`, `memory_usage`, `bandwidth`, `storage` |
| **Operational Trends** | `uptime`, `downtime`, `mean_time_between_failures`, `utilization_rate` |
| **Custom/Platform-Specific** | Platform-defined metrics mapped to generic categories |

**Additional Domain-Specific Extensions:**

For manufacturing/energy use cases (when applicable):
| **Energy** | `energy_per_unit`, `energy_total`, `peak_demand` |
| **Material** | `scrap_rate`, `rework_rate`, `material_efficiency` |
| **Production** | `oee`, `cycle_time`, `changeover_time` |
| **Carbon** | `co2_per_unit`, `co2_total` |

This ensures:
- Platform-independent skill logic
- Extensible framework for any operational domain
- Clear mapping requirements for new integrations
- Domain-specific metrics as optional extensions

---

## Component Specifications

### 1. OVOS Skill Layer (AVAROSSkill)

**Responsibility:** Intent recognition, slot extraction, response delivery

**Components:**
- Intent files for natural language patterns (Padatious format)
- Dialog files for response templates
- Skill handler methods for each query type
- Settings schema for UI-configurable options

**Query Type Coverage:**

| Query Type | Purpose | Example Utterances |
|------------|---------|-------------------|
| Status Query | Get current device/system state | "What's the status of device X?", "Is system Y online?" |
| Device Control | Turn on/off, start/stop systems | "Turn on device X", "Stop system Y" |
| Trend Visualization | Show performance over time | "Show trends", "How has system Y performed?" |
| Documentation Access | Retrieve help, guides, procedures | "What does this solution do?", "How do I configure X?" |
| Comparison | Compare metrics across entities | "Compare System A and B", "Which device is faster?" |
| Anomaly Check | Detect unusual patterns | "Any unusual patterns?", "Detect issues on system X" |
| What-If Simulation | Project impact of changes | "What if I change parameter X?", "Impact of threshold change?" |
| Maintenance Info | Get responsibility, schedule info | "Who maintains device X?", "When is next service?" |

**Workflow:**
1. OVOS matches user utterance to intent
2. Intent handler extracts parameters (asset ID, time period, etc.)
3. Handler calls QueryDispatcher with canonical concepts
4. Handler receives result and formats via ResponseBuilder
5. Voice response delivered to user

### 2. QueryDispatcher (Use Case Orchestrator)

**Responsibility:** Orchestrate queries across adapters AND intelligence services

**Key Principle:** QueryDispatcher coordinates all services - adapters for data, DocuBoT for grounding, PREVENTION for anomaly detection. Adapters never call intelligence services directly.

**Operations:**

| Operation | Orchestration Flow |
|-----------|-------------------|
| Get Data/Status | Adapter → ResponseBuilder |
| Execute Command | Adapter → ResponseBuilder |
| Compare | Adapter → ResponseBuilder |
| Get Trend | Adapter → ResponseBuilder |
| Check Anomaly | Adapter (raw data) → PREVENTION → ResponseBuilder |
| Simulate What-If | Adapter (reference data) → DocuBoT (grounding) → ResponseBuilder |
| Get Documentation | DocuBoT → ResponseBuilder |

**Cross-Cutting Concerns:**
- GDPR audit logging (query_id, user_role, timestamp, data_accessed)
- Error handling and fallback responses
- Async/sync bridging for OVOS compatibility
- Performance monitoring

### 3. PlatformAdapter Interface

**Responsibility:** Data transformation ONLY - fetch platform data and convert to universal format

**Core Operations (Data Only):**

| Operation | Purpose | Returns |
|-----------|---------|---------|
| Get Data | Retrieve current or historical metric value | Value, unit, timestamp, source |
| Execute Command | Perform device/system action (on/off, start/stop) | Status, confirmation, timestamp |
| Get Status | Retrieve current device/system state | Status, health, metadata |
| Compare | Compare metrics across multiple entities | Ranked items, winner, differences |
| Get Trend | Retrieve time-series data for a metric | Data points, direction, percent change |
| Get Raw Data | Provide time-series for PREVENTION analysis | Raw universal data points |

**Note:** `check_anomaly()` and `simulate_whatif()` are NOT adapter methods. These are orchestrated by QueryDispatcher using adapter data + intelligence services.

**Design Principles:**
- All inputs use universal operational concepts (not platform-specific terminology)
- All outputs use standardized result formats
- No platform-specific details leak into the interface
- Each adapter handles its own authentication and error handling

### 4. MockAdapter Implementation

**Responsibility:** Provide realistic demo data for zero-config deployment

**Characteristics:**
- No external dependencies (no API calls)
- Deterministic baseline values aligned with industry benchmarks
- Simulated trends using random walk with realistic bounds
- Occasional anomalies for demonstration purposes
- Instant responses (no I/O delay)

**Baseline Values (Examples):**
- Device status: "online" (85%), "offline" (5%), "degraded" (10%)
- System response time: 150ms average
- Resource utilization: CPU 45%, Memory 60%, Storage 70%
- Uptime: 99.2%
- Success rate: 97.5%

**Use Cases:**
- First-run experience before platform configuration
- Development and testing without backend dependencies
- Demonstrations and training
- Baseline for adapter implementation validation

### 5. RENERYOAdapter Implementation (Planned)

**Responsibility:** Data transformation ONLY - fetch RENERYO data and convert to canonical format

**Important:** This adapter does NOT call DocuBoT or PREVENTION. Those are orchestrated by QueryDispatcher at the Use Case layer. The adapter's sole job is platform data → canonical model transformation.

**Integration Points:**
- REST API endpoints for KPI retrieval
- Supplier data APIs
- Batch and lot tracking systems
- ERP/MES data aggregation layer

**Configuration-Driven Metric Mapping:**

The adapter uses configuration files (YAML/JSON) to map platform-specific fields to canonical metrics. This approach ensures:
- **New platforms = config change, not code change** - Adding a new backend only requires creating a mapping configuration
- **Platform independence** - The mapping is maintained separately from business logic
- **Flexibility** - Field mappings can be updated without code modifications

Example mapping concept:

| Platform Field | Canonical Metric | Unit Conversion |
|----------------|------------------|-----------------|
| `seu_hourly_kwh` | `energy_per_unit` | Divide by batch count |
| `waste_kg` | `scrap_rate` | Convert to percentage |
| `supplier_delivery_days` | `supplier_lead_time` | Direct mapping |
| `co2_emissions_total` | `co2_per_unit` | Divide by production count |

**Authentication & Security:**
- API credentials stored encrypted via SettingsService
- All external API calls use TLS 1.2+
- Token refresh and expiry handling
- Rate limiting compliance

**Error Handling:**
- Graceful degradation on partial data
- Clear error messages for missing configurations
- Fallback to cached data when available
- Retry logic with exponential backoff

### 6. DocuBoT Integration (Planned)

**Responsibility:** Retrieval-Augmented Generation for grounding recommendations in documentation

**Architectural Position:** Use Case Layer (platform-independent intelligence service)

**Data Sources:**
- Solution documentation and user guides
- System configuration procedures
- API documentation and developer guides
- Operational procedures and best practices
- Troubleshooting guides and FAQs
- Pilot experiment documentation and lessons learned

**Integration Approach:**
- **QueryDispatcher calls DocuBoT** (NOT the adapter) for grounding queries
- DocuBoT returns relevant document snippets with source links
- ResponseBuilder includes "Based on [Procedure XYZ-123]..." references
- Ensures transparency and traceability per EU AI Act requirements
- **Platform-independent:** Any adapter benefits from DocuBoT grounding automatically

**Indexing Strategy:**
- Document ingestion pipeline (PDF, DOCX, markdown)
- Semantic chunking for retrieval
- Version tracking for procedure changes
- Multilingual support (English, Turkish initially)

### 7. PREVENTION Integration (Planned)

**Responsibility:** Statistical anomaly detection and drift monitoring

**Architectural Position:** Use Case Layer (platform-independent intelligence service)

**Data Inputs:**
- Time-series metrics (response time, error rate, utilization, custom metrics)
- Baseline distributions from historical data
- Configurable thresholds per metric type

**Detection Methods:**
- Statistical process control (SPC) charts
- Isolation forest for multivariate anomalies
- Drift detection for distribution changes
- Configurable sensitivity levels

**Integration Approach:**
- **QueryDispatcher orchestrates:** fetches raw data via adapter, then calls PREVENTION
- Adapter provides time-series data in canonical format
- PREVENTION analyzes data and returns anomaly score, affected periods, severity
- AnomalyResult includes actionable context
- Alerts logged via AuditLogger for compliance
- **Platform-independent:** Any adapter's data can be analyzed by PREVENTION

**Alert Thresholds (Configurable):**
- Response time spike: >20% above rolling 7-day average
- Error rate: >1 standard deviation from baseline
- Resource utilization: >90% for extended period (>30 min)
- Availability drop: <95% SLA threshold

### 8. SettingsService

**Responsibility:** Database-backed configuration management

**Storage:**
- PostgreSQL database (production-grade from day one)
- SQLAlchemy ORM for database abstraction
- Docker-Compose includes PostgreSQL container with sensible defaults

**Configuration Categories:**
- Platform connection (type, URL, credentials)
- Data sources and connectors
- Alert thresholds and retention policies
- User roles and permissions (RBAC)

**Security Features:**
- Fernet encryption for API keys at rest
- Environment variable fallback for secrets
- Audit trail for configuration changes
- Role-based access control

**Hot-Reload:**
- AdapterFactory watches settings database
- Configuration changes trigger adapter recreation
- Zero-downtime reconfiguration
- Validation before applying changes

### 9. Web Configuration UI

**Responsibility:** Zero-config platform integration via browser-based forms

**Technology Stack:**
- Backend: FastAPI (Python) exposing REST API to SettingsService
- Frontend: React SPA with form validation and live connection testing
- Deployment: Separate Docker container (`avaros-web-ui:8080`)

**Key Features:**
- **First-Run Wizard:** 7-step flow from welcome to deployed configuration
- **Transport Support:** REST/JSON, MQTT, OPC-UA, CSV/Parquet with transport-specific forms
- **Pre-Built Templates:** RENERYO Manufacturing, Generic REST, IoT MQTT, Building Management
- **Live Validation:** Test connection button validates credentials and endpoint accessibility
- **Metric Mapper:** Drag-and-drop interface for canonical metric ↔ platform field mappings
- **DocuBoT Indexer:** Upload documents or point to folders; track indexing progress
- **PREVENTION Config:** Select monitored metrics, adjust sensitivity, configure alerts

**API Endpoints:**
```python
# Platform Configuration
POST   /api/v1/config/platform          # Create/update platform config
GET    /api/v1/config/platform          # Get current config
POST   /api/v1/config/platform/test     # Test connection (validates credentials)
DELETE /api/v1/config/platform          # Reset to MockAdapter

# Metric Mappings
POST   /api/v1/config/metrics           # Add metric mapping
GET    /api/v1/config/metrics           # List all mappings
GET    /api/v1/config/metrics/templates # Get pre-built templates
PUT    /api/v1/config/metrics/{id}      # Update mapping
DELETE /api/v1/config/metrics/{id}      # Remove mapping

# DocuBoT Configuration
POST   /api/v1/config/docubot           # Configure document sources
GET    /api/v1/config/docubot/status    # Indexing status and document count
POST   /api/v1/config/docubot/reindex   # Trigger re-indexing

# PREVENTION Configuration
POST   /api/v1/config/prevention        # Configure monitoring
GET    /api/v1/config/prevention/alerts # Get active alerts
PUT    /api/v1/config/prevention/thresholds  # Update thresholds
GET    /api/v1/config/prevention/metrics     # Get monitorable metrics
```

**Security:**
- API key authentication for backend API calls
- Credentials encrypted at rest (Fernet)
- RBAC: only admin role can modify platform config
- CORS configured for same-origin only (default)

**Proposal Alignment:**
> *"another SME will be able to point the assistant to its own sources with limited adaptation"*

The Web UI **IS** that "limited adaptation" - no code editing required.

### 10. Data Ingestion Service

**Responsibility:** Bridge push-based protocols (MQTT/OPC-UA/File) to pull-based adapter interface

**Architecture Challenge:**
- REST adapters pull data on-demand (synchronous)
- MQTT/OPC-UA push data continuously (asynchronous)
- Solution: Ingestion service subscribes to data sources and buffers in Redis

**Components:**
```python
class DataIngestionService:
    mqtt_subscriber: MQTTSubscriber      # Connects to broker, subscribes to topics
    opcua_monitor: OPCUANodeMonitor      # Monitors node value changes
    file_watcher: FileWatcher            # Watches import directory for CSV/Parquet
    time_series_buffer: RedisBuffer      # Rolling window cache (7-30 days)
    canonical_transformer: Transformer   # Maps incoming data to canonical format
```

**Data Flow:**
```
External Source → Ingestion Service → Redis Buffer → DataIngestionAdapter → QueryDispatcher
```

**MQTT Subscriber:**
- Connects to configured broker (URL, port, TLS settings)
- Subscribes to topics defined in metric mappings
- Transforms messages via JSONPath to canonical format
- Writes to Redis with timestamp and metric ID
- Auto-reconnect on connection failure

**OPC-UA Monitor:**
- Connects to OPC-UA server with configured security policy
- Subscribes to node value changes
- Transforms node values to canonical format
- Writes to Redis with timestamp and metric ID
- Certificate-based authentication support

**File Watcher:**
- Monitors import directory (`/data/imports/`)
- Detects new CSV/Parquet files
- Parses according to column mappings
- Writes parsed data to Redis
- Moves processed files to archive

**Time-Series Buffer (Redis):**
- Key pattern: `metric:{canonical_metric}:{entity_id}:{timestamp}`
- Rolling window: configurable (default 7 days, 30 days for manufacturing KPIs)
- Automatic eviction of old data
- Fast read access for trend and anomaly queries
- Optional persistence to disk for backup

**DataIngestionAdapter:**
- Implements same `ManufacturingAdapter` interface
- Queries Redis buffer instead of external API
- Returns data in identical canonical format
- Transparent to QueryDispatcher (doesn't know data source is buffered)

**Configuration via Web UI:**
```yaml
# MQTT Configuration Example
transport_type: mqtt
broker_url: mqtt://broker.factory.com
port: 1883
tls: true
topics:
  - topic: factory/machine/+/energy
    canonical_metric: energy_per_unit
    entity_id_pattern: machine/{machine_id}/energy  # Extract entity from topic
    json_path: $.value
    unit: kWh
buffer_retention_days: 30
```

**Benefits:**
- Unified pull-based interface for all transports
- Decouples AVAROS from push protocol complexity
- Enables trend and anomaly analysis on MQTT/OPC-UA data
- Handles intermittent connectivity gracefully
- No QueryDispatcher changes required

### 11. AuditLogger

**Responsibility:** GDPR-compliant immutable audit trails

**Logged Information:**
- query_id (UUID for traceability)
- timestamp (ISO 8601)
- user_role (NOT personal identifiers)
- query_type (kpi, compare, trend, anomaly, whatif)
- intent (e.g., "kpi.energy.per_unit")
- data_accessed (asset IDs, metrics queried)
- recommendation_id (for outcome tracking)
- response_summary (for transparency)

**Retention Policies:**
- Operational logs: 90 days rolling
- Audit logs: 1 year minimum
- Personal data: delete on user request
- Export capability for compliance audits

**Access Control:**
- Admin-only access to full audit logs
- User access to their own query history
- Immutable (append-only) storage
- Tamper-evident hashing

### 12. ResponseBuilder

**Responsibility:** Format Result objects into natural-language responses

**Capabilities:**
- Voice-optimized (under 30 words typical)
- Metric-specific recommendations
- Verbosity levels (brief, normal, detailed)
- Multilingual support (English, Turkish)

**Example Transformations:**
- KPIResult → "The OEE for Line-1 today is 82.5%, which is 3% above target."
- TrendResult → "Scrap rate decreased 15% over the last week."
- AnomalyResult → "I detected an energy spike on Machine-3 yesterday at 2 PM."
- WhatIfResult → "Reducing temperature by 5 degrees could save 8% energy with minimal quality impact."

**Recommendation Engine:**
- If metric below target → suggest improvement actions
- If anomaly detected → reference procedure via DocuBoT
- If what-if positive → highlight savings and confidence level
- Always include source attribution for transparency

---

## Zero-Config Web UI

### Web Configuration Interface

The Web UI is the **primary mechanism** for achieving the proposal's "limited adaptation" goal. It enables SMEs to integrate AVAROS with their platforms **without code editing**.

**Architecture:**
- Separate FastAPI container (`avaros-web-ui:8080`)
- React-based SPA for configuration forms
- RESTful API to SettingsService
- Hot-reload triggers adapter recreation on save

**First-Run Wizard Flow:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Welcome                                                │
│  └─ Explain AVAROS, zero-config philosophy, data flow           │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Step 2: Platform Selection                                     │
│  ☐ Mock (Demo Mode - No Platform Required)                     │
│  ☐ RENERYO (Manufacturing Optimization)                         │
│  ☑ Custom Platform (Generic REST/MQTT/OPC-UA/File)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Step 3: Connection Setup                                       │
│  Transport Type: [REST API ▼] MQTT | OPC-UA | File Import      │
│  Base URL: [https://api.example.com/v1____________]            │
│  Authentication: [API Key ▼] None | OAuth2 | Certificate       │
│  API Key: [••••••••••••••••••••••••••••••••_______]            │
│  [Test Connection]                                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Step 4: Metric Mapping                                         │
│  Use Template: [RENERYO Manufacturing ▼] Generic REST | Custom  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Canonical Metric     | Platform Endpoint   | JSONPath     │ │
│  │ energy_per_unit      | /kpis/energy        | $.data.value │ │
│  │ scrap_rate           | /production/scrap   | $.rate       │ │
│  │ supplier_lead_time   | /suppliers/{id}     | $.lead_days  │ │
│  │ [+ Add Mapping]                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Step 5: DocuBoT Setup                                          │
│  Document Sources: [/docs/procedures_______________] [Browse]  │
│  Index Schedule: [Daily ▼] Hourly | On-Demand                  │
│  [Skip] [Configure]                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Step 6: PREVENTION Setup                                       │
│  Monitored Metrics: ☑ energy_per_unit ☑ scrap_rate             │
│  Anomaly Sensitivity: [Medium ▼] Low | High                    │
│  Alert Threshold: [2 std deviations________]                   │
│  [Use Defaults] [Configure]                                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Step 7: Summary & Deploy                                       │
│  ✓ Platform: Custom REST API @ api.example.com                 │
│  ✓ Metrics: 12 mapped (energy, material, production)           │
│  ✓ DocuBoT: Indexing /docs/procedures                          │
│  ✓ PREVENTION: Monitoring 8 metrics                            │
│  [Deploy Configuration] [Back]                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Schema per Transport Type

**REST/JSON Configuration:**
```yaml
transport_type: rest
base_url: https://api.platform.com/v1
authentication:
  type: api_key
  header_name: X-API-Key
  key: <encrypted>
mappings:
  - canonical_metric: energy_per_unit
    endpoint: /energy/specific-units
    method: GET
    json_path: $.data.current_value
    unit: kWh/unit
    transform: null  # or: "value / batch_count"
```

**MQTT Configuration:**
```yaml
transport_type: mqtt
broker_url: mqtt://broker.platform.com
port: 1883
tls: true
topics:
  - topic: factory/machine/+/energy
    canonical_metric: energy_per_unit
    json_path: $.value
  - topic: factory/production/scrap
    canonical_metric: scrap_rate
    json_path: $.percentage
qos: 1
buffer_size: 10000  # Time-series cache size
```

**OPC-UA Configuration:**
```yaml
transport_type: opcua
server_url: opc.tcp://server.platform.com:4840
security_policy: Basic256Sha256
certificate_path: /certs/client.pem
node_mappings:
  - node_id: ns=2;s=Machine1.EnergyConsumption
    canonical_metric: energy_per_unit
  - node_id: ns=2;s=Production.ScrapCount
    canonical_metric: scrap_rate
    transform: "(value / total_production) * 100"
```

**CSV/Parquet File Import Configuration:**
```yaml
transport_type: file_import
file_path: /data/imports/daily_kpis.csv
format: csv
delimiter: ','
refresh_schedule: '0 2 * * *'  # Daily at 2 AM
column_mappings:
  - column_name: energy_kwh_per_unit
    canonical_metric: energy_per_unit
  - column_name: scrap_percentage
    canonical_metric: scrap_rate
date_column: timestamp
date_format: '%Y-%m-%d %H:%M:%S'
```

### Pre-Built Adapter Templates

**1. RENERYO Manufacturing Template:**
- Pre-mapped manufacturing metrics (energy, material, CO₂, production)
- REST API endpoints for RENERYO's KPI aggregation layer
- Supplier and batch tracking mappings
- Authentication: API Key + OAuth2 refresh

**2. Generic REST Template:**
- Common manufacturing metrics with placeholder endpoints
- Flexible JSONPath mappings
- Standard HTTP authentication methods
- User customizes endpoints, paths, and transforms

**3. IoT MQTT Template:**
- Topic patterns for device telemetry
- Time-series buffering configuration
- QoS and broker TLS settings

**4. Building Management Template:**
- Energy, HVAC, and occupancy metrics
- Typical BMS API patterns
- BACnet/OPC-UA bridge support

### SettingsService API Endpoints

```python
# Platform Configuration
POST   /api/v1/config/platform          # Create/update platform config
GET    /api/v1/config/platform          # Get current config
DELETE /api/v1/config/platform          # Reset to MockAdapter
POST   /api/v1/config/platform/test     # Test connection

# Metric Mappings
POST   /api/v1/config/metrics           # Add metric mapping
GET    /api/v1/config/metrics           # List all mappings
PUT    /api/v1/config/metrics/{id}      # Update mapping
DELETE /api/v1/config/metrics/{id}      # Remove mapping

# DocuBoT Configuration
POST   /api/v1/config/docubot           # Configure document sources
GET    /api/v1/config/docubot/status    # Indexing status
POST   /api/v1/config/docubot/reindex   # Trigger re-indexing

# PREVENTION Configuration
POST   /api/v1/config/prevention        # Configure monitoring
GET    /api/v1/config/prevention/alerts # Get active alerts
PUT    /api/v1/config/prevention/thresholds  # Update thresholds
```

---

## Transport Layer Architecture

### Handling Push-Based Protocols (MQTT/OPC-UA)

**Challenge:** REST is pull-based (AVAROS calls API); MQTT/OPC-UA are push-based (data arrives continuously).

**Solution:** Data Ingestion Service

```
┌──────────────────────────────────────────────────────────────┐
│  External Data Sources                                       │
│  ├── MQTT Broker (pub/sub topics)                           │
│  ├── OPC-UA Server (subscribed nodes)                       │
│  └── File Watcher (CSV/Parquet drops)                       │
└────────────────────────┬─────────────────────────────────────┘
                         │ push data
┌────────────────────────▼─────────────────────────────────────┐
│  Data Ingestion Service (avaros-ingestion container)        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  MQTT Subscriber                                        │ │
│  │  • Connects to broker, subscribes to topics            │ │
│  │  • Transforms incoming messages to canonical format    │ │
│  │  • Writes to time-series buffer                        │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  OPC-UA Subscriber                                      │ │
│  │  • Connects to server, monitors nodes                  │ │
│  │  • Transforms node values to canonical format          │ │
│  │  • Writes to time-series buffer                        │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  File Watcher                                           │ │
│  │  • Monitors import directory                           │ │
│  │  • Parses CSV/Parquet on file arrival                  │ │
│  │  • Writes to time-series buffer                        │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Time-Series Buffer (Redis)                            │ │
│  │  • Rolling window cache (configurable retention)       │ │
│  │  • Canonical metric format                             │ │
│  │  • Fast read access for QueryDispatcher               │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────────┘
                         │ pull via REST API
┌────────────────────────▼─────────────────────────────────────┐
│  Adapter (via DataIngestionAdapter)                         │
│  • Queries time-series buffer                               │
│  • Returns data in canonical format                         │
│  • Transparent to QueryDispatcher                           │
└──────────────────────────────────────────────────────────────┘
```

**Data Ingestion Service Responsibilities:**
- Subscribe to MQTT topics and transform messages
- Monitor OPC-UA nodes and buffer value changes
- Watch file import directory and parse on arrival
- Maintain rolling time-series cache (last 7-30 days configurable)
- Expose REST API for adapter queries
- Handle connection failures and automatic reconnection

**Benefits:**
- Unified pull-based interface for QueryDispatcher
- Decouples AVAROS from push protocol complexity
- Time-series buffering enables trend and anomaly analysis
- Graceful handling of intermittent connectivity

### Transport Matrix (Per WASABI Proposal Alignment)

| Transport | Proposal Reference | Configuration via Web UI | Data Flow |
|-----------|-------------------|-------------------------|-----------|
| **REST/JSON** | *"Operational data and KPIs will flow as JSON over REST"* | Base URL, endpoints, auth, JSONPath | Pull (Adapter → Platform) |
| **MQTT** | *"time-series from machines and sensors will be ingested via MQTT"* | Broker URL, topics, QoS, TLS | Push (Broker → Ingestion → Adapter) |
| **OPC-UA** | *"MQTT/OPC-UA bridges"* | Server URL, node IDs, security | Push (Server → Ingestion → Adapter) |
| **CSV/Parquet** | *"batch and supplier datasets will be imported/exported as CSV/Parquet"* | File path, schema, refresh schedule | File drop (Watcher → Ingestion → Adapter) |

**Architectural Guarantee:**
> Regardless of transport, all adapters return the same canonical data model. QueryDispatcher is transport-agnostic.

---

## Data Flow & Communication

### Query Flow Overview

All user queries follow a consistent pipeline regardless of the query type:

```
User Voice/Text → Intent Recognition → Slot Extraction → Query Dispatcher 
    → Adapter → Platform API → Canonical Result → Response Builder → Voice Response
```

**Key Stages:**
1. **Intent Recognition** - OVOS matches utterance to appropriate query type
2. **Slot Extraction** - Extract parameters (asset ID, time period, metric)
3. **Query Dispatch** - Route to appropriate adapter method with audit logging
4. **Platform Query** - Adapter calls external API and transforms response
5. **Response Formatting** - Build natural-language response with recommendations

### Example Query Flows

**Status Query:** "What's the status of Device-1?"
- Intent: Status retrieval for operational entity
- Slot: entity_id = "Device-1"
- Response: "Device-1 is online and healthy with 99.5% uptime."

**Comparison Query:** "Compare performance between System-A and System-B"
- Intent: Comparison across systems
- Slots: entity_ids = ["System-A", "System-B"], metric = performance
- Response: "System-B has 15% better performance with average response time of 120ms vs System-A at 140ms."

**Anomaly Query:** "Any unusual patterns on Device-3?"
- Intent: Anomaly detection check
- Slot: entity_id = "Device-3"
- Integration: Calls PREVENTION service for statistical analysis
- Response: "I detected a response time spike on Device-3 yesterday at 2 PM, 40% above normal. Review system logs per Troubleshooting Guide TG-045."

**What-If Query:** "What if I change the threshold parameter to 80%?"
- Intent: Scenario simulation
- Parameters: parameter = threshold, value = 80%
- Integration: Calls platform simulation + DocuBoT for documentation
- Response: "Changing threshold to 80% could reduce alert frequency by 25% with minimal impact on detection accuracy (85% confidence), per Configuration Guide CG-112."

---

## Implementation Phases

### Phase 1: Foundation (M1-M2)

**Deliverables:**
- Domain layer complete (Universal Metric Framework, Result types, exceptions)
- PlatformAdapter interface defined
- MockAdapter implementation with realistic demo data
- QueryDispatcher with audit logging
- SettingsService with database backend (PostgreSQL)
- ResponseBuilder for voice formatting
- Basic OVOS skill with Manufacturing Skill Pack intents (energy, scrap, supplier KPIs)
- **Web UI container (FastAPI + React)** with first-run wizard
- **Pre-built templates:** RENERYO + Generic REST
- Docker-Compose development stack

**Success Criteria:**
- User can ask manufacturing questions and receive voice responses
- MockAdapter returns realistic manufacturing KPI values
- Web UI accessible at `http://localhost:8080` with working wizard
- Platform configuration saved to database triggers MockAdapter → configured adapter switch
- Audit logs captured for all queries
- System runs via `docker compose up` without configuration

### Phase 2: Platform Integration & Transport Support (M3-M4)

**Deliverables:**
- RENERYO API documentation acquired and reviewed
- RENERYOAdapter implementation (REST/JSON)
- **Data Ingestion Service** for MQTT/OPC-UA (Python container)
- Generic metric mapping configuration (YAML-based)
- Platform authentication and credential management (encrypted)
- **Transport configuration UI** (REST/MQTT/OPC-UA/File)
- Error handling and retry logic
- Unit tests for adapter transformations
- Integration tests with RENERYO staging (or equivalent platform)

**Success Criteria:**
- AVAROS queries return real data from configured platform
- Metric transformations validated against universal model
- MQTT/OPC-UA data flows through ingestion service to adapters
- Web UI supports all four transport types
- Authentication and error handling robust
- Response times under 3 seconds for typical queries

### Phase 3: Intelligent Services & Advanced Configuration (M5-M6)

**Deliverables:**
- DocuBoT indexing pipeline operational
- DocuBoT integration in what-if scenarios
- PREVENTION service deployed
- PREVENTION integration in check_anomaly() flow
- Enhanced ResponseBuilder with document-grounded recommendations
- Web UI for settings configuration (first-run wizard)

**Success Criteria:**
- What-if responses include document references
- Anomaly detection uses PREVENTION statistical checks
- Users can configure platform settings via web interface
- Hot-reload works without container restarts

---

## Integration Strategy



### OVOS Stack Integration

**Components:**
- OVOS Core: Intent matching, skill lifecycle, dialog management
- OVOS Skills Manager: Skill installation and updates
- OVOS MessageBus: Inter-service communication
- OVOS Audio: TTS/STT backends

**Integration Points:**
- AVAROSSkill registers intents with Padatious
- Skill communicates via MessageBus events
- Asynchronous adapter calls bridged via event loop
- Health checks exposed for monitoring

**Deployment:**
- Official OVOS Docker-Compose project as base
- AVAROS skill added as mounted volume
- Environment variables for configuration
- Persistent volumes for settings database and audit logs

### DocuBoT Integration

**Architecture:**
- DocuBoT runs as separate container in stack
- REST API for indexing and retrieval
- Vector database for semantic search (e.g., Chroma, FAISS)
- Embedding model (sentence-transformers)

**Workflow:**
1. Indexing phase: Ingest procedures, specs, manuals
2. Query phase: QueryDispatcher sends query to DocuBoT API
3. DocuBoT returns top-k relevant chunks with source metadata
4. ResponseBuilder formats with document citations

**Data Sources:**
- Manufacturing SOPs (PDF, DOCX)
- Equipment manuals (PDF)
- Material specifications (PDF, CSV)
- Pilot documentation (markdown, DOCX)

### PREVENTION Integration

**Architecture:**
- PREVENTION runs as separate container in stack
- REST API for anomaly detection and drift monitoring
- Trained models for each metric type
- Configurable thresholds via API

**Workflow:**
1. Data ingestion: PREVENTION periodically pulls KPI time-series via configured adapter
2. Model training: Baseline distributions calculated from historical data
3. Query phase: QueryDispatcher calls PREVENTION check_anomaly() endpoint
4. PREVENTION returns anomaly score, affected timestamps, severity

**Metrics Monitored:**
- Energy per unit (statistical process control)
- Scrap rate (deviation from baseline)
- Supplier lead time (drift detection)
- Machine throughput (isolation forest)

### RENERYO Platform Integration

**API Endpoints (Planned):**
- `/api/kpi/current` - Get latest KPI values
- `/api/kpi/historical` - Time-series data
- `/api/suppliers` - Supplier performance data
- `/api/batches` - Batch and lot tracking
- `/api/simulate` - What-if scenario simulation

**Authentication:**
- API key-based authentication
- Bearer token in Authorization header
- Token refresh mechanism for long-running sessions

**Data Transformation:**
- RENERYO metric names → CanonicalMetric mapping
- Unit normalization (kWh, kg, %, hours)
- Timestamp standardization (ISO 8601)
- Error code translation to domain exceptions

**Rate Limiting & Caching:**
- Respect RENERYO rate limits (e.g., 100 requests/minute)
- Cache frequently-accessed data (TTL: 5 minutes)
- Batch queries where possible
- Exponential backoff on 429 responses

---

## Security & Compliance

### GDPR Compliance

**Data Minimization:**
- Collect ONLY data necessary for manufacturing optimization
- NO personal data unless authentication requires it
- Pseudonymize user IDs in logs where feasible

**Audit Logging:**
- Immutable (append-only) audit trail
- query_id, timestamp, user_role (NOT personal identifiers)
- Data accessed (assets, metrics), recommendations given
- Retention: 90 days operational, 1 year audit

**Data Retention:**
- Operational logs: 90 days rolling
- Audit logs: 1 year minimum
- Personal data (if any): delete on user request
- Right to access: users can export their query history

**Access Control (RBAC):**

| Role | Permissions |
|------|-------------|
| Operator | Query KPIs, view trends |
| Planner | + What-if simulations |
| Engineer | + Anomaly investigation, detailed analysis |
| Admin | + Configuration, audit review, user management |

### EU AI Act Compliance (Limited Risk)

**Human Oversight:**
- User ALWAYS makes final decision
- Recommendations include confidence level and evidence
- Clear escalation paths documented
- No automated actions without user confirmation

**Transparency:**
- Explain WHY recommendation was made
- Link to DocuBoT sources (procedures, specs)
- Show input features used in analysis
- Model version tracked for every prediction

**Risk Management:**
- Log model versions for every prediction
- Track recommendation outcomes when available
- Flag high-uncertainty outputs (confidence < 70%)
- Periodic validation against ground truth

### Security Controls (ISO/IEC 27001-aligned)

**Authentication & Authorization:**
- TLS 1.2+ for all API calls
- API keys via environment variables (never in code)
- JWT tokens with expiry for user sessions
- Role-based access control enforced at API layer

**Secrets Management:**
- NEVER commit credentials to repository
- Use Docker secrets or environment variables
- Fernet encryption for API keys in database
- Key rotation procedures documented

**Encryption:**
- At rest: encrypted volumes for database and logs
- In transit: TLS everywhere (HTTPS, secure WebSocket)
- Backups: encrypted before storage
- Key management: separate from application data

**Code Implementation Rules:**
1. Add `@audit_log` decorator to handlers accessing sensitive data
2. Include `user_role` in all API requests
3. Return `recommendation_id` with every suggestion
4. Log but NEVER expose raw credentials in errors
5. Implement graceful degradation on auth failures

---

## User Interaction Model

### Voice Widget for Web Applications

**Deployment Approach:** AVAROS provides a JavaScript widget that can be embedded in any web application, enabling zero-friction adoption.

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Any Web Application                          │
│                (RENERYO, MES, BMS, Custom Dashboard)            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  <script src="http://avaros-host:8080/widget.js"></script>│  │
│  │                                                           │  │
│  │         ┌─────────────────────────────┐                   │  │
│  │         │    AVAROS Voice Widget      │                   │  │
│  │         │  🎤 [Ask AVAROS...]  [Send] │                   │  │
│  │         │  ─────────────────────────  │                   │  │
│  │         │  💬 Response appears here   │                   │  │
│  │         └─────────────────────────────┘                   │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │ REST API (HTTPS)
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                     AVAROS Docker Stack                           │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                        nginx                                │   │
│  │  /              → Settings Web UI                           │   │
│  │  /widget.js     → AVAROS Widget (embeddable)               │   │
│  │  /api/*         → REST Bridge                               │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│  ┌───────────────────────────▼───────────────────────────────┐    │
│  │                    REST Bridge (FastAPI)                   │    │
│  │  POST /api/query    → Process natural language query       │    │
│  │  GET  /api/health   → Health check                         │    │
│  │  WS   /api/stream   → Streaming responses (optional)       │    │
│  └───────────────────────────┬───────────────────────────────┘    │
│                              │                                     │
│  ┌───────────────────────────▼───────────────────────────────┐    │
│  │              OVOS Core + AVAROSSkill                       │    │
│  │  (Intent recognition, QueryDispatcher, Adapters)           │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**Integration for Adopters:**

```html
<!-- Add AVAROS Voice Assistant to any page -->
<script 
  src="http://your-avaros-host:8080/widget.js"
  data-position="bottom-right"
  data-theme="light"
></script>
```

**Widget Features:**
- Voice input via Web Speech API (browser microphone)
- Text input as fallback
- Audio + text responses
- Configurable positioning (bottom-right, bottom-left, etc.)
- Theming support (light/dark/custom)
- Mobile-responsive
- No external dependencies (self-contained)

**Zero-Config Benefits:**
- No source code access required to target application
- Works with ANY web-based system
- Single line of code to enable voice assistant
- Portable across different solutions
- Matches zero-touch deployment philosophy

**CORS & Security:**
- Configurable allowed origins via Settings UI
- Token-based authentication for API calls
- Domain-based allowlist for widget embedding
- RBAC enforced server-side

---

## Deployment Architecture

### Docker-Compose Stack

**Complete Container Architecture:**

| Service | Container | Purpose | Ports |
|---------|-----------|---------|-------|
| **ovos-core** | `ovos/ovos-core:latest` | OVOS framework for intent matching and dialog management | 8181 (MessageBus) |
| **avaros-skill** | `avaros/skill:latest` | Custom skill container with business logic and adapters | Internal |
| **avaros-web-ui** | `avaros/web-ui:latest` | FastAPI backend + React SPA for configuration | 8080 (HTTP) |
| **avaros-ingestion** | `avaros/ingestion:latest` | MQTT/OPC-UA subscriber + time-series buffer | Internal |
| **docubot** | `wasabi/docubot:latest` | RAG retrieval service for document grounding | 8000 (API) |
| **prevention** | `wasabi/prevention:latest` | Anomaly detection service | 8001 (API) |
| **database** | `postgres:15-alpine` | Settings and audit database (production-grade) | 5432 (internal) |
| **redis** | `redis:7-alpine` | Time-series buffer for ingestion service + API cache | 6379 (internal) |

**Data Flow Between Containers:**
```
User Browser → avaros-web-ui:8080 → database (settings CRUD)
                                  ↓ triggers hot-reload
User Voice   → ovos-core:8181 → avaros-skill (intent handlers)
                                  ↓ calls
                            QueryDispatcher → RENERYOAdapter (REST)
                                  ↓           OR
                            QueryDispatcher → DataIngestionAdapter → redis (MQTT/OPC-UA data)
                                  ↓
                            QueryDispatcher → docubot:8000 (grounding)
                                  ↓
                            QueryDispatcher → prevention:8001 (anomaly check)

External MQTT Broker → avaros-ingestion (subscriber) → redis (buffer)
External OPC-UA Server → avaros-ingestion (monitor) → redis (buffer)
```

**Persistent Storage:**
- PostgreSQL database (via Docker volume) - Platform configurations, metric mappings, audit logs (encrypted credentials)
- `/data/docubot_index/` - DocuBoT vector embeddings and document chunks
- `/data/prevention_models/` - PREVENTION baseline models and thresholds
- `/data/ingestion_buffer/` - Redis persistence (optional, for time-series backup)

**Environment Configuration (Minimal):**
```yaml
# .env.example - ALL variables have defaults, editing optional
AVAROS_WEB_UI_PORT=8080          # Default: 8080
AVAROS_LOG_LEVEL=INFO            # Default: INFO
POSTGRES_PASSWORD=<generated>    # Auto-generated on first run
REDIS_MAXMEMORY=256mb            # Default: 256mb
INGESTION_BUFFER_DAYS=7          # Default: 7 days rolling window
# NO platform credentials here - configured via Web UI
```

**Networking:**
- All services in `avaros-network` Docker bridge network
- Only ports 8080 (Web UI) and 8181 (OVOS MessageBus) exposed to host
- Internal service-to-service communication via Docker DNS
- TLS termination at nginx (optional, for production)

### Zero-Config First Run

**Experience:**
1. User runs `docker compose up -d`
2. System starts with MockAdapter active
3. Web UI opens at `http://localhost:8080`
4. First-run wizard appears:
   - Welcome and explanation
   - Platform selection (RENERYO, Mock, Custom)
   - If RENERYO: enter credentials (tested immediately)
   - Optional: import sample data
5. Settings saved to database (encrypted)
6. AdapterFactory hot-reloads new adapter
7. User can immediately start querying

**No File Editing Required:**
- No YAML configs to edit
- No code changes needed
- No manual database setup
- Settings via Web UI only

### Health Checks & Monitoring

**Container Health:**
- Each service exposes `/health` endpoint
- Docker health checks every 30 seconds
- Automatic restart on failure
- Graceful shutdown handling

**Application Health:**
- OVOS skill registration status
- Adapter connection status (RENERYO, DocuBoT, PREVENTION)
- Database connectivity
- Audit log write verification

**Monitoring Endpoints:**
- `/metrics` - Prometheus-compatible metrics
- `/status` - Human-readable system status
- `/logs` - Recent log tail (admin only)

### Backup & Recovery

**Backup Strategy:**
- Settings database: daily automated backup
- Audit logs: incremental append-only backup
- Model files: backup on version change

**Recovery Procedures:**
- Database corruption: restore from latest backup
- Adapter failure: automatic fallback to MockAdapter
- Service crash: Docker restart policy

---

**End of Document**
