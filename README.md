# AVAROS — AI Voice Assistant for Resource-Optimized Sustainable Manufacturing

**AVAROS** is an OVOS-based conversational AI assistant that gives manufacturing teams voice access to energy, material, supply chain, and carbon KPIs — plus anomaly detection and drift monitoring via the PREVENTION analytics platform.

> **WASABI OC2 Experiment** — 12-month timeline (started Feb 2026)  
> **Current Phase:** WP2 — DIA Development (OVOS + PREVENTION + Docker-Compose)  
> **Last Updated:** April 9, 2026  
> **Team:** Mohamad (Lead / Architect) · Emre (Developer)

---

## What is AVAROS?

AVAROS lets manufacturing teams ask questions like:

```
"What's our energy per unit this week?"
"Compare Supplier A and Supplier B on defect rates"
"Show me the scrap rate trend for the last month"
"Are there any anomalies?"                          ← PREVENTION anomaly scan
"Is energy per unit drifting on Line-1?"             ← PREVENTION drift check
"Check for unusual carbon patterns on Line-2"        ← targeted anomaly check
```

### Key Capabilities

| Category | What It Does |
|----------|-------------|
| **KPI Queries** | Energy, production, material, carbon, supplier metrics per asset and period |
| **Trend Analysis** | Time-series trends with daily/weekly/monthly granularity |
| **Comparison** | Side-by-side asset comparison ("Line-1 vs Line-2 on scrap rate") |
| **Anomaly Detection** | Z-score analysis via PREVENTION — flags unusual spikes/dips with sigma deviation |
| **Drift Monitoring** | Linear regression via PREVENTION — detects gradual KPI degradation |
| **What-If Scenarios** | "What happens if temperature goes to 220?" simulation |
| **Voice + Web UI** | OVOS voice interface + FastAPI/React web dashboard |

### Supported Metrics (19 canonical)

| Energy | Production | Material | Carbon | Supplier |
|--------|-----------|----------|--------|----------|
| `energy_per_unit` | `oee` | `scrap_rate` | `co2_per_unit` | `supplier_lead_time` |
| `energy_total` | `throughput` | `rework_rate` | `co2_total` | `supplier_defect_rate` |
| `peak_demand` | `cycle_time` | `material_efficiency` | `co2_per_batch` | `supplier_on_time` |
| `peak_tariff_exposure` | `changeover_time` | `recycled_content` | | `supplier_co2_per_kg` |

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                    Voice / Web UI                 │
│   OVOS Skill  ←→  FastAPI + React Dashboard      │
└──────────┬───────────────────────────┬───────────┘
           │                           │
    ┌──────▼──────┐            ┌───────▼───────┐
    │  Query      │            │  Response     │
    │  Dispatcher │            │  Builder      │
    │  (DEC-007)  │            │               │
    └──────┬──────┘            └───────────────┘
           │
    ┌──────▼──────┐     ┌──────────────────┐
    │  Adapters   │     │  PREVENTION      │
    │  (DEC-001)  │     │  (GraphQL)       │
    │  RENERYO /  │     │  Anomaly + Drift │
    │  any REST   │     │  5 categories    │
    └─────────────┘     └──────────────────┘
```

**Design Decisions (DEC-001 to DEC-007)** — full details in [DEVELOPMENT.md](DEVELOPMENT.md):

| DEC | Principle | Summary |
|-----|-----------|---------|
| DEC-001 | Platform-Agnostic | No platform names in handlers/domain/use_cases |
| DEC-002 | Universal Metrics | Canonical names only (`energy_per_unit`, not `seu`) |
| DEC-003 | Clean Architecture | Domain never imports from infrastructure |
| DEC-004 | Immutable Models | All domain models use `frozen=True` |
| DEC-005 | Zero-Config | Works without config files (UnconfiguredAdapter fallback) |
| DEC-006 | Settings Service | Credentials via SettingsService, never hardcoded |
| DEC-007 | Smart Orchestration | Adapters fetch data; intelligence in QueryDispatcher |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development)

### Start AVAROS

```bash
git clone ssh://git@git.arti.ac/europe/AVAROS.git
cd AVAROS

# Start main AVAROS stack (7 services)
docker compose up -d

# Start PREVENTION analytics (2 services)
docker compose -f docker/docker-compose.prevention.yml up -d

# Verify all 9 containers are healthy
docker compose ps
docker compose -f docker/docker-compose.prevention.yml ps
```

### Services

| Container | Port | Purpose |
|-----------|------|---------|
| `avaros-skill` | — | OVOS skill (main logic) |
| `avaros-ovos-core` | — | OVOS intent engine |
| `avaros-messagebus` | 8181 | OVOS message bus (WebSocket) |
| `avaros-wakeword` | — | "Hey AVAROS" wake word detection |
| `avaros-web-ui` | 8080 | FastAPI + React web dashboard |
| `avaros-hivemind` | 5678 | HiveMind satellite gateway |
| `reneryo-data-generator-api` | 8090 | RENERYO mock data API |
| `prevention` | 8083 | PREVENTION GraphQL analytics |
| `prevention-mongo` | — | MongoDB for PREVENTION |

### First Run

AVAROS works out-of-the-box with the UnconfiguredAdapter. Run the web wizard at `http://localhost:8080` to connect to a REST platform (RENERYO, EnergySuite, or any JSON/REST API). Provide API URL, auth credentials, and metric mappings through the unified wizard.

### Web UI API Key

Web UI routes require `AVAROS_WEB_API_KEY`:

```bash
# Set in project root .env
AVAROS_WEB_API_KEY=your-strong-key

# Recreate services
docker compose up -d --force-recreate avaros-web-ui avaros-skill

# Validate
curl -i http://localhost:8080/api/v1/status -H "X-API-Key: your-strong-key"
```

### Environment Variables

Use `.env.example` as template. Key variables:

| Variable | Purpose |
|----------|---------|
| `AVAROS_WEB_API_KEY` | Web UI API authentication |
| `PREVENTION_URL` | PREVENTION endpoint (leave empty to disable analytics) |
| `PREVENTION_AUTH_TOKEN` | Bearer token for Keycloak (optional) |
| `PREVENTION_DATA_MAX_AGE_MINUTES` | Stale-data threshold for PREVENTION export manifests |
| `HIVEMIND_MASTER_KEY` | HiveMind auth (auto-generated if empty) |
| `AVAROS_DATABASE_URL` | SQLite/PostgreSQL for SettingsService |

Full reference: [docs/ENV-REFERENCE.md](docs/ENV-REFERENCE.md)

---

## PREVENTION Integration

AVAROS integrates the [PREVENTION](https://2smart.2smart.2smart) analytics platform (by ICCS) for anomaly detection and drift monitoring.

### How It Works

1. **Data Export**: Adapter time-series data is exported to 5 JSON files plus an `export_manifest.json` freshness manifest
2. **PREVENTION Addon**: The AVAROS addon (`tools/prevention-addon/`) loads data into MongoDB and configures 10 analytics goals
3. **Pre-Computation**: PREVENTION runs z-score anomaly detection and linear regression drift analysis at startup
4. **Voice Queries**: `HttpPreventionClient` queries PREVENTION's GraphQL API, filters by metric and asset, and translates results into voice responses

### Analytics Goals (10 total)

| Category | Anomaly Check | Drift Check |
|----------|--------------|-------------|
| Energy | `ENERGY_ANOMALY_CHECK` | `ENERGY_DRIFT_CHECK` |
| Production | `PRODUCTION_ANOMALY_CHECK` | `PRODUCTION_DRIFT_CHECK` |
| Material | `MATERIAL_ANOMALY_CHECK` | `MATERIAL_DRIFT_CHECK` |
| Carbon | `CO2_ANOMALY_CHECK` | `CO2_DRIFT_CHECK` |
| Supplier | `SUPPLIER_ANOMALY_CHECK` | `SUPPLIER_DRIFT_CHECK` |

### Runtime Truthfulness

- AVAROS treats PREVENTION as **disabled** when no URL is configured.
- AVAROS reports PREVENTION as **healthy** or **unreachable** only after a live health check.
- The Web UI status endpoint also reports PREVENTION input data freshness from `tools/prevention-addon/data/export_manifest.json`.

### Understanding Anomaly Results

When AVAROS says *"peak tariff exposure dipped at 2.9 sigma"*, the sigma (σ) value is the **z-score** — how many standard deviations the reading is from the mean:

| Sigma | Meaning | Roughly how rare |
|-------|---------|-----------------|
| < 2.0σ | Normal range | Common |
| 2.0–2.5σ | Unusual (low severity) | ~5% of readings |
| 2.5–3.0σ | Significant (medium severity) | ~1% of readings |
| 3.0–4.0σ | Major (high severity) | ~0.3% of readings |
| > 4.0σ | Critical | Extremely rare |

---

## Project Structure

```
avaros-ovos-skill/
├── skill/                      # OVOS skill code
│   ├── __init__.py             # Main skill class (AVAROSSkill)
│   ├── _handlers.py            # Fallback query handlers
│   ├── _metric_handlers.py     # KPI/anomaly/drift/trend handlers
│   ├── _slot_resolution.py     # Asset and slot extraction from utterances
│   ├── _intent_resolver.py     # Intent routing logic
│   ├── domain/                 # Domain layer (DEC-003: no infra imports)
│   │   ├── models.py           # CanonicalMetric, TimePeriod, etc. (frozen=True)
│   │   ├── results.py          # KPIResult, TrendResult, AnomalyResult, etc.
│   │   ├── anomaly_models.py   # AnomalyDetectionResult, DriftReport
│   │   └── exceptions.py       # AVAROSError hierarchy
│   ├── adapters/               # Platform adapters (DEC-001)
│   │   ├── base.py             # ManufacturingAdapter ABC
│   │   ├── generic_rest/       # GenericRestAdapter (works with any REST API)
│   │   ├── unconfigured.py     # UnconfiguredAdapter (zero-config)
│   │   └── factory.py          # AdapterFactory
│   ├── clients/                # External service clients
│   │   ├── prevention.py       # PreventionClient ABC
│   │   ├── prevention_http.py  # HttpPreventionClient (GraphQL)
│   │   └── docubot.py          # DocuBotClient (RAG — planned)
│   ├── use_cases/              # Orchestration (DEC-007)
│   │   └── query_dispatcher.py # Routes queries, applies intelligence
│   ├── services/               # Support services
│   │   ├── settings.py         # SettingsService (DEC-006)
│   │   ├── audit.py            # Immutable audit trail
│   │   ├── alert_monitor.py    # Proactive alert scheduling
│   │   └── response_builder.py # Voice response formatting
│   └── locale/en-us/           # 35 intent files + dialog templates
├── tools/
│   ├── prevention-addon/       # PREVENTION addon (analytics goals + data loader)
│   └── prevention-data-sync/   # Adapter → PREVENTION data exporter + manifest
├── tests/                      # 1,491 tests (pytest)
├── web-ui/                     # FastAPI + React dashboard
├── docker/                     # Docker artifacts
│   ├── Dockerfile              # AVAROS skill container
│   ├── Dockerfile.prevention   # Legacy local PREVENTION image artifact
│   ├── docker-compose.avaros.yml
│   └── docker-compose.prevention.yml  # PREVENTION development/no-auth overlay
├── docker-compose.yml          # Main compose (7 services)
├── DEVELOPMENT.md              # Coding standards (1,300+ lines)
└── README.md
```

---

## Testing

```bash
# Run all unit/integration tests
python3 -m pytest tests/ --ignore=tests/test_e2e -v

# Quick summary
python3 -m pytest tests/ --ignore=tests/test_e2e -q

# With coverage
python3 -m pytest tests/ --cov=skill --cov-report=html

# Voice E2E tests (requires running Docker stack)
docker exec avaros-skill python3 /tmp/voice_test.py
```

**Current stats:** 1,491 passed, 0 failed

### Coverage Targets

| Layer | Target |
|-------|--------|
| Domain models | 100% |
| Use cases | 95%+ |
| Adapters | 90%+ |
| Handlers | 80%+ |

---

## Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [DEVELOPMENT.md](DEVELOPMENT.md) | Developers | Coding standards, DEC decisions, conventions |
| [Pilot Playbook](docs/PILOT-PLAYBOOK.md) | Operators | Step-by-step deployment guide |
| [Voice Commands](docs/VOICE-COMMANDS.md) | Operators | Printable voice command card |
| [ENV Reference](docs/ENV-REFERENCE.md) | Operators / Devs | All environment variables |
| [PREVENTION Evaluation](docs/PREVENTION-EVALUATION-REPORT.md) | WASABI | Formal PREVENTION audit & compliance |
| [WASABI Proposal](docs/WASABI_2Call_AVAROS_Proposal.md) | WASABI | Original WASABI OC2 experiment proposal |

---

## WASABI KPI Targets

| KPI | Target | Method |
|-----|--------|--------|
| Electricity per unit reduction | ≥ 8% | Energy optimization via voice-guided scheduling |
| Material efficiency improvement | ≥ 5% | Scrap/rework reduction via early anomaly detection |
| CO₂-eq reduction | ≥ 10% | Carbon tracking + supplier performance monitoring |

---

## Development Workflow

### Team Roles
- **Mohamad (Lead):** Architecture, task planning, code review, merge/deploy
- **Emre (Developer):** Implementation — domain, adapters, services, handlers, tests, Docker, Web UI

### Git
- Feature branches → Pull Requests → Review → Merge
- Commit format: `<type>(<scope>): <subject>` (e.g., `feat(prevention): add drift monitoring`)
- Remotes: `origin` (Forgejo) + `github` (GitHub mirror)

---

## License

This project is licensed under Apache-2.0. See [LICENSE](LICENSE).

---

**Built for sustainable manufacturing — WASABI OC2 Experiment**
