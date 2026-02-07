# AVAROS Overview

> **AI-Voice-Assistant-Driven Resource-Optimized Sustainable Manufacturing**

---

## What is AVAROS?

AVAROS is a voice-enabled AI assistant for manufacturing environments. It allows engineers, planners, and operators to access real-time production data, energy metrics, supplier performance, and sustainability KPIs through natural conversation—no dashboards or spreadsheets required.

**Example interactions:**

> 🗣️ "What's our energy consumption per unit this week?"  
> 🤖 "Energy per unit this week is 12.3 kilowatt-hours, down 5% from last week."

> 🗣️ "Compare Supplier A and Supplier B on delivery performance"  
> 🤖 "Supplier A delivers on time 94% versus Supplier B at 87%. Supplier A also has 2 days shorter lead time."

> 🗣️ "Any unusual patterns in production today?"  
> 🤖 "I detected an energy spike on Line 2 around 10 AM—15% above normal. This may indicate a maintenance issue."

---

## Why AVAROS?

### The Problem

Manufacturing decisions happen throughout the day—supplier choices, schedule adjustments, quality responses. But the data needed for these decisions is:

- **Fragmented** across ERP, MES, sensor systems, and spreadsheets
- **Slow to access** requiring logins, queries, and report generation
- **Expertise-dependent** trapped in the heads of experienced staff

### The Solution

AVAROS brings the data to the user through conversation. Instead of searching for information, users simply ask questions in plain language and receive immediate, contextualized answers.

---

## Target Benefits

| KPI | Target |
|-----|--------|
| Electricity per unit | ≥8% reduction |
| Material efficiency | ≥5% improvement |
| CO₂ emissions | ≥10% reduction |

These improvements come from faster decisions, earlier anomaly detection, and better visibility into resource consumption patterns.

---

## How It Works

### The Big Picture

```
                    ┌─────────────────────┐
                    │       USER          │
                    │  (Voice or Text)    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       AVAROS        │
                    │   Voice Assistant   │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │   DocuBoT   │     │  DocuBoT   │     │ PREVENTION  │
   │  Documents  │     │    Data     │     │  Anomalies  │
   └─────────────┘     └─────────────┘     └─────────────┘
```

1. **User** asks a question via voice or text
2. **AVAROS** understands the question and determines what data is needed
3. **Data sources** provide the answer:
   - **Platform Data** — Real-time KPIs from RENERYO (or other manufacturing systems)
   - **DocuBoT** — Procedures, specifications, and reference documents
   - **PREVENTION** — Anomaly alerts and early warnings
4. **AVAROS** responds in natural language

---

## Five Ways to Ask

AVAROS understands five types of questions:

| Type | What You Ask | What You Get |
|------|--------------|--------------|
| **KPI** | "What's our scrap rate?" | Current metric value with trend |
| **Compare** | "Compare Line 1 vs Line 2" | Side-by-side ranking |
| **Trend** | "Show energy trend this month" | Direction and pattern analysis |
| **Anomaly** | "Any problems today?" | Unusual patterns detected |
| **What-If** | "What if we switch suppliers?" | Predicted impact |

---

## Core Concepts

### Manufacturing Metrics

AVAROS speaks the language of manufacturing, not databases. You ask about concepts you already know:

| Category | Example Metrics |
|----------|-----------------|
| **Energy** | Energy per unit, peak demand, tariff exposure |
| **Materials** | Scrap rate, rework rate, recycled content |
| **Suppliers** | Lead time, defect rate, on-time delivery |
| **Production** | OEE, throughput, cycle time, changeover time |
| **Carbon** | CO₂ per unit, total emissions, batch carbon |

### Platform Independence

AVAROS works with your existing systems. The initial deployment connects to **RENERYO** (ArtiBilim's supply-chain and energy optimization platform), but the architecture is designed to work with any Energy Management System (EnMS) or manufacturing data platform:

**EnMS Platforms:**
- ISO 50001-compliant Energy Management Systems
- RENERYO (supply chain + energy optimization)
- Custom EnMS implementations
- Energy monitoring dashboards

**Data Integration:**
- ERP/MES systems (ISO 50001 EnMS, generic platforms, custom)
- IIoT sensor networks via MQTT/OPC-UA
- Supplier data feeds (CSV, REST APIs)
- LCA databases and emission factors

**How Platform Switching Works:**

AVAROS achieves platform independence through a **Web-based Configuration UI**—no code editing required:

1. **First Run**: AVAROS starts with MockAdapter (demo mode with realistic sample data)
2. **Setup Wizard**: Open Web UI at `http://localhost:8080/setup`
3. **Platform Selection**: Choose your platform type from dropdown:
   - RENERYO
   - Generic EnMS (REST API)
   - CSV/File Import
   - Custom Connector
4. **Credential Entry**: Enter API URL, API key (stored encrypted)
5. **Test Connection**: Validate connectivity and data access
6. **Metric Mapping**: Map your platform's metrics to AVAROS canonical metrics
7. **Activate**: AVAROS hot-reloads with new adapter—no container restart

Configuration is stored in a database, not files. Changes take effect immediately. You can switch platforms or run multiple adapters simultaneously (e.g., RENERYO for energy, CSV for supplier data).

### Zero Configuration Start

AVAROS works immediately after installation:

```
git clone → docker compose up → start asking questions
```

Out of the box, AVAROS runs with demo data so you can explore all features. When ready, connect your real data through a simple setup wizard—no code editing required.



## Key Components

### AVAROS Skill (Voice Layer)

The **AVAROS Skill** is the entry point for all user interactions. It's built as an **OVOS skill**—a plugin for the Open Voice OS framework.

**What the Skill Does:**

1. **Intent Recognition**
   - Listens to user utterances (voice or text)
   - Matches utterances to one of five query type intents
   - Extracts parameters: metric name, time period, asset ID, supplier name
   - Example: "Show energy trend this week" → Intent: `trend.energy`, Period: `this_week`

2. **Query Orchestration**
   - Routes recognized intent to Query Dispatcher
   - Waits for result from platform adapter
   - Handles errors gracefully with fallback dialogs

3. **Response Formatting**
   - Converts data results to natural language
   - Keeps voice responses under 30 words (attention span)
   - Provides longer context via follow-up questions
   - Example: "Energy per unit is 12.3 kilowatt-hours, down 5%." (not: "The value of the ENERGY_PER_UNIT metric for the current week time period is...")

4. **Multi-Turn Conversations**
   - Remembers context within conversation session
   - Supports clarifying questions: "Tell me more" → Provides detailed breakdown
   - Handles ambiguity: "Which supplier?" → Lists options

**Technology:** Python-based skill extending OVOSSkill base class, using Padatious for intent matching.

### Platform Adapters: The Translation Layer

The **Adapter pattern** is AVAROS's key architectural innovation for platform independence. Each adapter is a specialized translator that understands both:

1. **AVAROS's language**: Universal manufacturing concepts (energy per unit, scrap rate, supplier lead time)
2. **Platform's language**: Specific API endpoints, data formats, authentication methods

#### How Adapters Work

**Every adapter implements five methods** corresponding to the five query types:

| Method | Purpose | Example |
|--------|---------|---------| 
| `get_kpi()` | Fetch single metric value | "What's our OEE?" → Query platform's OEE endpoint → Return 82.5% |
| `compare()` | Rank multiple entities | "Compare suppliers" → Fetch supplier data → Return ranked list |
| `get_trend()` | Time-series analysis | "Energy trend" → Fetch hourly data → Return trend with direction |
| `check_anomaly()` | Detect outliers | "Any problems?" → Query PREVENTION → Return detected anomalies |
| `simulate_whatif()` | Predict impact | "If we switch suppliers?" → Run simulation model → Return prediction |

**Adapter Lifecycle:**

```
User asks question
       ↓
AVAROS recognizes intent
       ↓
Query Dispatcher routes to adapter method
       ↓
Adapter translates to platform API call
       ↓
Platform returns data
       ↓
Adapter translates to canonical result format
       ↓
AVAROS speaks answer
```

#### Available Adapters

| Adapter | Status | Purpose |
|---------|--------|----------|
| **MockAdapter** | ✅ Production | Zero-config demo mode with realistic synthetic data. Works out-of-the-box for exploration and training. |
| **RENERYOAdapter** | 🔄 In Development | Production connection to RENERYO platform (energy, supply chain, batch tracking). First real-world adapter. |
| **GenericEnMSAdapter** | 📋 Planned | Configurable adapter for ISO 50001 EnMS platforms. User defines metric mappings via Web UI. |
| **CSVAdapter** | 📋 Planned | Import data from CSV/Excel files. Useful for offline analysis or legacy systems. |
| **Custom Adapters** | 🔧 Extensible | Organizations can develop adapters for proprietary systems using the adapter template. |

#### Creating a New Adapter

For organizations with custom EnMS or MES systems, creating an adapter is straightforward:

1. **Implement the interface**: Extend `ManufacturingAdapter` base class
2. **Define metric mapping**: Map AVAROS canonical metrics to your API endpoints (configuration file)
3. **Handle authentication**: Implement your platform's auth (API key, OAuth, etc.)
4. **Register**: Add adapter to factory registry
5. **Test**: Use included test suite to validate five query types
6. **Deploy**: Select your adapter in Web UI

Typical development time: 2-5 days for experienced developers with API documentation.

#### Why Adapters Matter

**Without adapters**: Each manufacturing platform would require rewriting AVAROS's core logic. Utterances like "What's our energy per unit?" would need platform-specific handlers.

**With adapters**: AVAROS's core logic remains unchanged. The adapter translates "energy per unit" to whatever your platform calls it (`kWh_per_unit`, `specific_energy_consumption`, etc.). This means:

- ✅ **One AVAROS codebase** works with any platform
- ✅ **Same voice commands** regardless of backend
- ✅ **New platforms** don't break existing functionality
- ✅ **Multi-platform** deployments (hybrid adapters)
- ✅ **Community adapters** can be shared via WASABI Shop

### DocuBoT (Document Intelligence)

**DocuBoT** is AVAROS's knowledge retrieval component, developed by the WASABI consortium. It provides **Retrieval-Augmented Generation (RAG)**—answers grounded in your actual documents, not generic AI responses.

**What DocuBoT Does:**

1. **Document Indexing**
   - Ingests procedures, specifications, manuals, supplier declarations
   - Breaks documents into semantic chunks
   - Creates vector embeddings for similarity search
   - Supports multiple languages (English, German, Turkish)

2. **Retrieval on Demand**
   - When AVAROS receives a procedural question, it queries DocuBoT
   - DocuBoT searches its vector database for relevant passages
   - Returns top-k most relevant chunks with confidence scores
   - Includes source attribution (document name, page, section)

3. **Answer Grounding**
   - Generates answer based ONLY on retrieved documents
   - Cites sources explicitly
   - Returns "I don't have documentation on that" if no relevant content found
   - Never invents information

**Example Interaction:**

> 🗣️ "What's the maximum changeover time for Line 1?"  
> 🤖 "According to SOP-2023-045, maximum changeover time is 15 minutes. Source: Quality Manual, Section 4.2."
>
> 🗣️ "Why does Supplier B have higher defect rates?"
> 🤖 "Supplier B's Quality Report from Q4 2025 notes moisture control issues during transport. Defect rate: 2.3% vs target 1.5%. Source: Supplier-B-Q4-Report.pdf, page 7."

**Indexed Document Types:**
- Standard Operating Procedures (SOPs)
- Equipment manuals and maintenance schedules
- Quality standards (ISO, industry-specific)
- Supplier declarations and certifications
- LCA (Life Cycle Assessment) methodology documents
- Emission factor tables
- Training materials

**Integration:** DocuBoT runs as a separate service in the Docker-Compose stack. AVAROS communicates with it via REST API. Document updates are indexed automatically when uploaded via Web UI.

**Privacy:** Documents never leave your infrastructure. DocuBoT runs entirely on-premises within your Docker environment.

### PREVENTION (Anomaly Detection & Early Warning)

**PREVENTION** is AVAROS's proactive monitoring component, also from the WASABI consortium. While you can ask AVAROS "Any problems today?", PREVENTION works continuously in the background, analyzing time-series data streams for anomalies.

**What PREVENTION Does:**

1. **Continuous Monitoring**
   - Ingests real-time data from platform (energy consumption, production rates, quality metrics)
   - Runs statistical anomaly detection algorithms
   - Identifies patterns that deviate from expected baselines
   - Operates 24/7 without human intervention

2. **Anomaly Detection Methods**
   - **Statistical**: Z-score analysis, moving averages, seasonal decomposition
   - **Rule-based**: Threshold violations (e.g., energy > 120% of baseline)
   - **Trend drift**: Gradual shifts that indicate deteriorating performance
   - **Pattern recognition**: Unusual time-of-day or day-of-week patterns

3. **Severity Classification**
   - **INFO** (1-2σ): Minor deviation, logged but no alert
   - **WARNING** (2-3σ): Notify user when they next interact with AVAROS
   - **CRITICAL** (>3σ): Immediate proactive interrupt: "I detected an urgent issue..."

4. **Root Cause Hints**
   - PREVENTION doesn't just say "anomaly detected"
   - Provides context: "Energy spike on Line 2, coincides with changeover start"
   - Suggests investigation steps: "Check hydraulic pressure logs"

**Example Interactions:**

**Reactive (User asks):**
> 🗣️ "Any unusual patterns today?"  
> 🤖 "Yes, I detected an energy spike on Line 2 at 10:15 AM—15% above normal. This occurred during a mold changeover and lasted 12 minutes. Previous changeovers averaged 8 minutes. Recommend checking setup procedure."

**Proactive (PREVENTION interrupts):**
> 🤖 "⚠️ Urgent: CO₂ per unit has been trending up 3% per day for the last 5 days on Line 3. Current value: 2.8 kg versus target 2.4 kg. This may indicate calibration drift or material quality issues."

**Integration Modes:**

1. **On-Demand**: AVAROS queries PREVENTION when user asks about anomalies
2. **Webhook**: PREVENTION sends alerts to AVAROS via HTTP callback when critical issues detected
3. **Batch Summary**: PREVENTION generates daily/shift summaries for routine review

**Configuration:**
- Thresholds customizable per metric via Web UI
- Notification preferences (immediate, batched, silent)
- Alert history and false-positive feedback to improve detection

**Why This Matters:** Traditional dashboards require operators to watch for problems. PREVENTION watches for you, freeing human attention for decision-making, not monitoring.

---

## OVOS (Open Voice OS)

**OVOS** is the open-source voice assistant framework that powers AVAROS's conversational interface. Think of it as the "operating system" for voice interaction.

**What OVOS Provides:**

1. **Speech-to-Text (STT)**
   - Converts spoken words into text
   - Supports multiple STT engines (Whisper, Coqui, cloud services)
   - Works offline for privacy-sensitive deployments

2. **Intent Parsing**
   - Analyzes text to understand user's goal
   - Extracts parameters (dates, numbers, names)
   - Handles natural language variations: "What's the energy today?" = "Show me today's power consumption" = "Energy for today"

3. **Text-to-Speech (TTS)**
   - Converts AVAROS's responses back to speech
   - Natural-sounding voices
   - Multilingual support

4. **Skills Framework**
   - AVAROS is implemented as an OVOS skill (like apps on a smartphone)
   - Skills can be added/removed independently
   - Other skills can run alongside AVAROS (timer, weather, etc.)

5. **Message Bus**
   - Internal communication backbone
   - Event-driven architecture
   - Allows different components to interact without tight coupling

**Why OVOS Instead of Alexa/Google?**

| Feature | OVOS | Commercial Assistants |
|---------|------|----------------------|
| **Privacy** | Runs entirely on-premises | Cloud-dependent, data leaves your network |
| **Customization** | Full control over behavior | Limited to vendor's API |
| **Industrial Focus** | Can be hardened for factory environments | Consumer-focused |
| **Offline Operation** | Works without internet | Requires internet connection |
| **Integration** | Direct access to internal systems | Must use vendor's cloud gateway |

**AVAROS ↔ OVOS Relationship:**
- OVOS handles **how** the conversation happens (speech, understanding, speaking)
- AVAROS handles **what** the conversation is about (manufacturing data, KPIs, decisions)
- They work together: OVOS is the "mouth and ears", AVAROS is the "brain"

---

## System Architecture

AVAROS is built on a **layered architecture** that separates concerns and ensures each component can evolve independently.

### Architectural Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│                    (Voice, Text, Web UI)                            │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                      PRESENTATION LAYER                             │
│                         (OVOS + AVAROS Skill)                       │
│  ┌────────────────┐  ┌─────────────────┐  ┌────────────────────┐  │
│  │ Speech-to-Text │→ │ Intent Handlers │→ │ Response Formatter │  │
│  └────────────────┘  └────────┬────────┘  └────────────────────┘  │
└─────────────────────────────────│─────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                       USE CASE LAYER                                │
│  ┌──────────────────┐  ┌────────────┐  ┌─────────────────────┐    │
│  │ Query Dispatcher │  │ Audit Log  │  │ Settings Service    │    │
│  │  (Routes by      │  │ (GDPR)     │  │ (Configuration DB)  │    │
│  │   query type)    │  └────────────┘  └─────────────────────┘    │
│  └─────────┬────────┘                                              │
└────────────│───────────────────────────────────────────────────────┘
             │
             │         ┌──────────────┐          ┌──────────────┐
             ├────────►│   DocuBoT    │          │  PREVENTION  │
             │         │   (RAG)      │          │  (Anomaly)   │
             │         └──────────────┘          └──────────────┘
             │
┌────────────▼─────────────────────────────────────────────────────────┐
│                      ADAPTER LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ MockAdapter  │  │ RENERYO      │  │ Generic EnMS / Custom    │  │
│  │ (Demo)       │  │ Adapter      │  │ Adapters                 │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   RENERYO    │  │  Other EnMS  │  │  ERP/MES/Sensors        │  │
│  │   Platform   │  │  Platforms   │  │  (MQTT/OPC-UA/REST)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**1. Presentation Layer (OVOS + AVAROS Skill)**
- Handles all user interaction
- Speech recognition and synthesis
- Intent recognition: "What's our energy?" → GET_KPI query
- Response formatting: Data → Natural language
- **Knows:** How to talk to users
- **Doesn't know:** Where data comes from, how to fetch it

**2. Use Case Layer (Query Dispatcher, Services)**
- Orchestrates business logic
- Routes queries to appropriate adapters
- Manages audit logging (every query recorded)
- Handles configuration and settings
- **Knows:** The five query types, orchestration logic
- **Doesn't know:** Platform-specific APIs, data formats

**3. Adapter Layer (Platform Translators)**
- Translates between AVAROS concepts and platform APIs
- Each adapter knows one platform's language
- Implements five standard methods (get_kpi, compare, etc.)
- Returns results in canonical format
- **Knows:** Platform APIs, authentication, data mapping
- **Doesn't know:** How AVAROS will use the data, voice formatting

**4. External Systems (Data Sources)**
- Your existing manufacturing infrastructure
- RENERYO, other EnMS, ERP, MES, sensors
- AVAROS connects via standard protocols (REST, MQTT, OPC-UA)

### Data Flow Example: "What's our energy per unit this week?"

```
1. USER speaks → "What's our energy per unit this week?"
                 ↓
2. OVOS (STT) → "what's our energy per unit this week" (text)
                 ↓
3. OVOS Intent → Matches: kpi.energy.per_unit.intent
                 Slots: metric=ENERGY_PER_UNIT, period=this_week
                 ↓
4. AVAROS Skill → Calls: QueryDispatcher.get_kpi(ENERGY_PER_UNIT, this_week)
                 ↓
5. Query Dispatcher → Logs audit entry
                      Gets active adapter (RENERYOAdapter)
                      Calls: adapter.get_kpi(ENERGY_PER_UNIT, this_week)
                 ↓
6. RENERYOAdapter → Maps: ENERGY_PER_UNIT → "specific_energy_consumption"
                     Calls: RENERYO API endpoint /api/v1/kpi/energy?period=...
                     Receives: {"value": 12.3, "unit": "kWh", "delta": -5}
                     Translates to: KPIResult(value=12.3, unit="kWh", delta_pct=-5)
                 ↓
7. Query Dispatcher → Returns KPIResult to Skill
                 ↓
8. AVAROS Skill → Formats: "Energy per unit this week is 12.3 kilowatt-hours, down 5%"
                 ↓
9. OVOS (TTS) → Speaks response
                 ↓
10. USER hears → "Energy per unit this week is 12.3 kilowatt-hours, down 5%"
```

### Communication Protocols

| Connection | Protocol | Security |
|------------|----------|----------|
| User ↔ OVOS | Audio / WebSocket | Local network |
| OVOS ↔ AVAROS Skill | OVOS Message Bus (internal) | In-process |
| Skill ↔ Query Dispatcher | Python function calls | In-process |
| Dispatcher ↔ Adapters | Python async calls | In-process |
| Adapter ↔ RENERYO | HTTPS REST/JSON | TLS 1.2+, API key |
| Skill ↔ DocuBoT | HTTPS REST/JSON | TLS 1.2+, internal network |
| Skill ↔ PREVENTION | HTTPS REST/JSON | TLS 1.2+, internal network |
| Sensors → RENERYO | MQTT / OPC-UA | TLS (if supported by devices) |

### Why This Architecture?

**Separation of Concerns:**
- Voice experts work on OVOS layer without touching data logic
- Manufacturing domain experts work on canonical metrics without touching adapters
- Integration specialists work on adapters without touching voice

**Platform Independence:**
- AVAROS core never changes when adding new platforms
- New adapter = new platform support
- Can run multiple adapters simultaneously (multi-source queries)

**Testability:**
- Each layer can be tested independently
- MockAdapter allows full system testing without real platform
- Unit tests for each component

**Compliance:**
- Audit logging at orchestration layer (all queries logged)
- Security controls at adapter layer (credentials, encryption)
- Privacy at presentation layer (no PII in logs)

**Maintainability:**
- Clear boundaries between components
- Changes in one layer don't break others
- New features can be added without rewriting existing code

---

## Deployment

AVAROS runs as a containerized application using Docker Compose:

```
┌─────────────────────────────────────────┐
│           Docker Compose Stack          │
│  ┌───────────┐  ┌───────────┐          │
│  │  AVAROS   │  │   OVOS    │          │
│  │   Skill   │  │   Core    │          │
│  └───────────┘  └───────────┘          │
│  ┌───────────┐  ┌───────────┐          │
│  │  DocuBoT  │  │PREVENTION │          │
│  └───────────┘  └───────────┘          │
│  ┌───────────┐                         │
│  │ Database  │                         │
│  └───────────┘                         │
└─────────────────────────────────────────┘
```

**Requirements:**
- Docker and Docker Compose
- 4GB RAM minimum
- Network access to your manufacturing platform

---

## Security & Compliance

AVAROS is designed for industrial environments with appropriate controls:

| Requirement | How AVAROS Addresses It |
|-------------|------------------------|
| **GDPR** | Audit logging without personal identifiers, data minimization |
| **EU AI Act** | Human oversight, explainable recommendations, confidence indicators |
| **Data Security** | Encrypted credentials, TLS for all connections, role-based access |
| **Traceability** | Every query logged with unique ID for audit trail |

---

## Implementation Roadmap

| Phase | Duration | Focus |
|-------|----------|-------|
| **Foundation** | Weeks 1-4 | Core architecture, demo mode |
| **Services** | Weeks 5-8 | Settings, audit, response quality |
| **Integration** | Weeks 9-14 | RENERYO, DocuBoT, PREVENTION |
| **Deployment** | Weeks 15-18 | Production readiness, Web UI |
| **Pilot** | Weeks 19-24 | Validation, KPI measurement, publication |

---

## Who Uses AVAROS?

| Role | Typical Questions |
|------|-------------------|
| **Production Planner** | "What's the schedule impact if we run third shift?" |
| **Quality Engineer** | "Show me defect trends for the last month" |
| **Energy Manager** | "Which line had the highest energy consumption?" |
| **Procurement** | "Compare our top 3 suppliers on delivery and quality" |
| **Plant Manager** | "Give me today's OEE summary" |

---

## Summary

AVAROS transforms manufacturing data access from a search-and-report exercise into a conversation. By connecting voice interaction with real-time manufacturing data, document knowledge, and anomaly detection, it helps teams make better decisions faster—contributing to measurable improvements in energy efficiency, material usage, and carbon footprint.

**Key differentiators:**
- ✅ Voice-first design for shop floor usability
- ✅ Platform-agnostic architecture
- ✅ Zero-configuration startup
- ✅ Document-grounded answers
- ✅ Proactive anomaly alerts
- ✅ GDPR and AI Act compliant

---

*Part of the WASABI White-Label Shop for Digital Intelligent Assistance*

*Document Version: 1.0 | February 2026*
