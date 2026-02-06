# AVAROS - AI Voice Assistant for Manufacturing

**AVAROS** (AI-Voice-Assistant-Driven Resource-Optimized Sustainable Manufacturing) is an OVOS-based conversational AI assistant that provides manufacturing teams with voice-accessible KPIs for energy, materials, supply chain, and carbon metrics.

> **Status:** Phase 1 Complete (Deployment & Integration)  
> **Last Updated:** February 6, 2026  
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
# - http://localhost:5000 (coming in Phase 2)
```

### First Run (Zero-Config)
AVAROS works out-of-the-box with mock data:
- No configuration files to edit
- Demo KPIs available immediately
- Perfect for testing and learning

### Connect to Real Platform
Configuration is done via the Web UI (Phase 2) or Settings API. Supports RENERYO and other energy management platforms with REST/MQTT/OPC-UA interfaces.

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
├── docker/                     # Docker artifacts
│   ├── Dockerfile             # AVAROS container
│   └── docker-compose.avaros.yml  # AVAROS service definition
└── README.md                   # This file
```

---

## 🏗️ Architecture Principles

AVAROS follows [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) with strict layer separation:

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

Detailed documentation is maintained locally for development purposes. For architecture and deployment information, refer to code comments and Docker configuration files.

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

### Phase 2: Intelligence Layer (Planned)
- [ ] DocuBoT integration (RAG for procedures/specs)
- [ ] PREVENTION service (anomaly detection)
- [ ] RENERYO adapter implementation
- [ ] Web UI (React dashboard)

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
