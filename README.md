# AVAROS - AI Voice Assistant for Manufacturing

**AVAROS** (AI-Voice-Assistant-Driven Resource-Optimized Sustainable Manufacturing) is an OVOS-based conversational AI assistant that provides manufacturing teams with voice-accessible KPIs for energy, materials, supply chain, and carbon metrics.

> **Status:** Phase 4 — Dual Pilots, KPI Measurement & Data Completeness  
> **Last Updated:** February 12, 2026  
> **Team:** Mohamad (Lead) + Emre (Developer)

---

## 🎯 What is AVAROS?

AVAROS lets manufacturing teams ask questions like:
- "What's our energy per unit this week?"
- "Compare Supplier A and Supplier B on defect rates"
- "Show me the scrap rate trend for the last 3 months"
- "Are there any unusual patterns in production?"

### Key Features
- 🎤 **Voice-first interface** via OVOS (Open Voice OS)
- 📊 **Platform-agnostic design** - works with RENERYO, EnergySuite, GreenMetrics, or any energy/manufacturing platform
- 📈 **Universal metrics** - canonical manufacturing concepts (energy_per_unit, scrap_rate, oee)
- 🔒 **GDPR-compliant** - audit trails, RBAC, data minimization
- 🐳 **Docker-based deployment** - easy setup and scaling

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)
- Git

### Clone and Run

```bash
# Clone the repository
git clone https://code.arti.ac/europe/AVAROS.git
cd AVAROS

# Start AVAROS with Docker
docker compose up

# AVAROS Web UI will be available at:
# - http://localhost:8080 (FastAPI + built frontend)
# - http://localhost:5173 (Vite development server)
```

### First Run (Zero-Config)
AVAROS works out-of-the-box with mock data:
- No configuration files to edit
- Demo KPIs available immediately
- Perfect for testing and learning

### Connect to Real Platform
Configuration is done via the Web UI wizard or Settings API. Supports `mock`, `reneryo`, and `custom_rest` platform profiles in the current setup flow.

### Web UI API Key Auth (Required)
Web UI API routes are protected by `AVAROS_WEB_API_KEY`.

1. Set key in project root `.env`:
```bash
AVAROS_WEB_API_KEY=your-strong-key
```

2. Start/recreate services with the AVAROS compose file:
```bash
docker compose -f docker/docker-compose.avaros.yml up -d --force-recreate avaros-web-ui avaros_skill
```

3. Validate API auth:
```bash
curl -i http://localhost:8080/api/v1/status \
  -H "X-API-Key: your-strong-key"
```

If you get `401 Invalid or missing API key`, check `avaros-web-ui` logs and verify the value in `.env`.

### Environment Variables and Secret Handling
- Use `.env.example` as the template for local `.env`.
- Keep credentials out of tracked files (compose/YAML/HTML/docs).
- `HIVEMIND_MASTER_KEY`, `HIVEMIND_CLIENT_KEY`, `HIVEMIND_CLIENT_SECRET`, and
  `HIVEMIND_CLIENT_CRYPTO_KEY` can be left empty for local runs; the HiveMind
  entrypoint will auto-generate values at startup and log them.
- For shared/staging/production environments, set explicit strong values in `.env`.

### Troubleshooting: Voice shows "disabled"
- If voice appears disabled right after changing `AVAROS_WEB_API_KEY`, the browser may still be using an old key from local storage.
- Re-enter the API key in the UI (or clear browser storage) and refresh the page.
- Confirm backend config is reachable:

```bash
curl -i http://localhost:8080/api/v1/voice/config \
  -H "X-API-Key: <your-key>"
```

Expected: `200 OK` and `"voice_enabled": true`.

---

## 📁 Project Structure

```
avaros-ovos-skill/
├── skill/                      # OVOS skill code
│   ├── __init__.py            # Main skill class with intent handlers
│   ├── domain/                # Platform-agnostic business logic
│   │   ├── models.py          # Domain models (KPIResult, TimeFrame, etc.)
│   │   ├── results.py         # Result types (TrendResult, ComparisonResult)
│   │   └── exceptions.py      # Custom exceptions
│   ├── adapters/              # Backend platform adapters
│   │   ├── base.py            # ManufacturingAdapter interface (ABC)
│   │   ├── mock.py            # MockAdapter (demo data, zero-config)
│   │   └── factory.py         # Adapter factory (selects based on config)
│   ├── use_cases/             # Orchestration layer
│   │   └── query_dispatcher.py  # Routes queries, adds intelligence
│   ├── services/              # Support services
│   │   ├── settings.py        # SettingsService (config management)
│   │   ├── audit.py           # AuditService (GDPR compliance)
│   │   └── response_builder.py  # Dialog response formatting
│   └── locale/                # Intents and dialogs
├── tests/                      # Test suite (pytest)
├── web-ui/                     # FastAPI + React web interface
│   ├── main.py                # FastAPI app entry point
│   ├── routers/               # API routers (status/config/metrics)
│   ├── schemas/               # Pydantic response/request models
│   ├── dependencies.py        # Shared dependency injection
│   └── frontend/              # Vite + React + TypeScript frontend
├── docker/                     # Docker artifacts
│   ├── Dockerfile             # AVAROS container
│   └── docker-compose.avaros.yml  # AVAROS service definition
└── README.md                   # This file
```

---

## 🏗️ Architecture Principles

AVAROS follows [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) with strict layer separation.

**📖 Complete development standards:** See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed guidelines, code examples, and best practices.

### Design Decisions (DEC-001 to DEC-007)

| DEC | Principle | Why It Matters |
|-----|-----------|----------------|
| **DEC-001** | Platform-Agnostic Design | Works with ANY energy/manufacturing platform |
| **DEC-002** | Universal Metric Framework | Canonical names (`energy_per_unit` not platform-specific terms) |
| **DEC-003** | Clean Architecture | Domain never imports infrastructure |
| **DEC-004** | Immutable Domain Models | Thread-safe, predictable (`frozen=True`) |
| **DEC-005** | Zero-Config First Run | `docker compose up` → working system |
| **DEC-006** | Settings Service Pattern | No hardcoded credentials |
| **DEC-007** | Intelligence in Orchestration | Adapters are dumb data fetchers |

**Full details with code examples:** [DEVELOPMENT.md](DEVELOPMENT.md)

---

## 🧪 Testing

### Run Tests
```bash
# Unit tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=skill --cov-report=html

# E2E voice test (requires Docker)
python test_e2e.py
```

### Test Coverage Targets
- Domain models: 100%
- Adapters: 90%+
- Use cases: 95%+
- Overall: 80%+

---

## 👥 Development Workflow

### Team Structure
- **Mohamad (Lead):** Architecture, domain layer, adapters, orchestration
- **Emre (Developer):** Web UI, intents, dialogs, tests, Docker

### Git Workflow
- Protected `main` branch - NO direct pushes
- Feature branches: `feature/lead-P1-L05-github-setup` or `feature/emre-P1-E01-unit-tests`
- All changes via Pull Requests
- Merge strategies:
  - **Squash** for Emre (cleaner history)
  - **Rebase** for Lead (preserves atomic commits)
  - **Merge commit** for large features

### Commit Message Format
```
<type>(<scope>): <subject>

<body>

Closes P1-L05
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`  
**Scopes:** `domain`, `adapters`, `skill`, `web`, `services`, `devops`

---

## 📚 Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [Pilot Deployment Playbook](docs/PILOT-PLAYBOOK.md) | Operators | Step-by-step deployment and operations guide (D3.1) |
| [Environment Variable Reference](docs/ENV-REFERENCE.md) | Operators / Devs | All `.env` configuration variables |
| [Voice Commands Quick Reference](docs/VOICE-COMMANDS.md) | Operators | Printable voice command card |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Developers | Coding standards and architecture decisions |
| [Security Checklist](docs/SECURITY-CHECKLIST.md) | Developers | ISO 27001–aligned security audit |

---

## 🎓 Getting Started

1. **Read this README** (you are here! ✅)
2. **Clone and run:** `git clone https://code.arti.ac/europe/AVAROS.git` → `cd AVAROS` → `docker compose up`
3. **Explore the architecture:** Understand domain models, adapters, and use cases
4. **Run tests:** `pytest tests/ -v`
5. **Check assigned issues:** Tasks are managed via Forgejo issues/kanban board

**Note:** Work on feature branches, submit PRs for review.

---

## 🔐 Security & Compliance

- **GDPR-by-design:** Audit logs, RBAC, data minimization
- **TLS for all API calls**
- **No hardcoded credentials** - use SettingsService
- **Immutable audit trails** for recommendations

---

## 🗺️ Roadmap

### Phase 1: Deployment & Integration ✅
- [x] Deploy WASABI OVOS locally
- [x] AVAROS Docker integration
- [x] Skill loads in OVOS
- [x] End-to-end voice test
- [x] Forgejo repository setup

### Phase 2: Intelligence Layer (In Progress)
- [x] Web UI service scaffold (FastAPI container)
- [x] Health & system status API
- [x] Platform configuration CRUD API
- [x] Metric mapping CRUD API
- [x] React frontend shell (Vite + TypeScript)
- [x] First-run wizard (3-step MVP)
- [ ] DocuBoT integration (RAG for procedures/specs)
- [ ] PREVENTION service (anomaly detection)
- [ ] RENERYO adapter implementation

### Phase 3: Production Hardening (Planned)
- [ ] Multi-platform adapters (additional energy management systems)
- [ ] Advanced queries (What-If scenarios)
- [ ] WASABI Consortium integration
- [ ] Turkish localization (tr-tr)

---

## 📄 License

*[License information to be added]*

---

## 🤝 Contributing

This is a private repository for the AVAROS development team. For external contributions, please contact the project lead.

### Team Members
- **Mohamad (Lead):** Architecture & Core Development
- **Emre (Developer):** UI, Intents & Testing

---

**Built with ❤️ for sustainable manufacturing**
