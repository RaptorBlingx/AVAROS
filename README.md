# AVAROS - AI Voice Assistant for Manufacturing

**AVAROS** (AI-Voice-Assistant-Driven Resource-Optimized Sustainable Manufacturing) is an OVOS-based conversational AI assistant that provides manufacturing teams with voice-accessible KPIs for energy, materials, supply chain, and carbon metrics.

> **Status:** Phase 1 Complete (Deployment & Integration)  
> **Last Updated:** February 6, 2026  
> **Team:** Lead Developer + Emre (Junior Developer)

---

## 🎯 What is AVAROS?

AVAROS lets manufacturing teams ask questions like:
- "What's our energy per unit this week?"
- "Compare Supplier A and Supplier B on defect rates"
- "Show me the scrap rate trend for the last 3 months"
- "Are there any unusual patterns in production?"

### Key Features
- 🎤 **Voice-first interface** via OVOS (Open Voice OS)
- 📊 **Platform-agnostic design** - works with RENERYO, SAP, Siemens MindSphere, etc.
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
git clone https://github.com/YOURUSERNAME/avaros-ovos-skill.git
cd avaros-ovos-skill

# Start AVAROS with Docker
docker compose up

# The system will be available at:
# - OVOS GUI: http://localhost:8181
# - AVAROS Web UI: http://localhost:5000 (coming in Phase 2)
```

### First Run (Zero-Config)
AVAROS works out-of-the-box with mock data:
- No configuration files to edit
- Demo KPIs available immediately
- Perfect for testing and learning

### Connect to Real Platform (RENERYO, SAP, etc.)
Configuration is done via the Web UI (Phase 2) or Settings API. See [docs/DEPLOYMENT-SETUP.md](docs/DEPLOYMENT-SETUP.md) for details.

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
│   └── locale/                # Intents and dialogs (en-us, tr-tr coming)
├── tests/                      # Test suite (pytest)
├── docker/                     # Docker artifacts
│   ├── Dockerfile             # AVAROS container
│   └── docker-compose.avaros.yml  # AVAROS service definition
├── docs/                       # Documentation
│   ├── AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md
│   ├── TODO.md                # Active task list
│   ├── DECISIONS.md           # Architecture decision log
│   └── tasks/                 # Detailed task specifications
└── .github/
    ├── agents/                # Custom Copilot agents
    │   ├── planner.md         # @planner agent
    │   ├── lead-dev.md        # @lead-dev agent
    │   ├── quality.md         # @quality agent
    │   ├── pr-review.md       # @pr-review agent
    │   └── git.md             # @git agent
    └── instructions/          # Protocol documentation
```

---

## 🏗️ Architecture Principles

AVAROS follows [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) with strict layer separation:

### Design Decisions (DEC-001 to DEC-007)

| DEC | Principle | Why It Matters |
|-----|-----------|----------------|
| **DEC-001** | Platform-Agnostic Design | Works with ANY backend (RENERYO, SAP, etc.) |
| **DEC-002** | Universal Metric Framework | Canonical names (`energy_per_unit` not `seu`) |
| **DEC-003** | Clean Architecture | Domain never imports infrastructure |
| **DEC-004** | Immutable Domain Models | Thread-safe, predictable (`frozen=True`) |
| **DEC-005** | Zero-Config First Run | `docker compose up` → working system |
| **DEC-006** | Settings Service Pattern | No hardcoded credentials |
| **DEC-007** | Intelligence in Orchestration | Adapters are dumb data fetchers |

**Full details:** [docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md](docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md)

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
- **Lead Developer:** Architecture, domain layer, adapters, orchestration
- **Emre (Junior Developer):** Web UI, intents, dialogs, tests, Docker

### Custom Agents
AVAROS uses 5 specialized GitHub Copilot agents:

| Agent | Purpose | Example |
|-------|---------|---------|
| `@planner` | Task planning, TODO generation | `@planner Create Phase 2 TODO` |
| `@lead-dev` | Lead developer tasks | `@lead-dev Do task P1-L05` |
| `@quality` | Expert code review | `@quality Review P1-L04` |
| `@pr-review` | Emre's PR review + teaching | `@pr-review Review PR #5` |
| `@git` | Git operations with approval | `@git Create PR for P1-L04` |

**See:** [docs/AGENT-SYSTEM-PLAN.md](docs/AGENT-SYSTEM-PLAN.md)

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

| Document | Purpose |
|----------|---------|
| [GETTING-STARTED.md](GETTING-STARTED.md) | Development workflow guide |
| [docs/TODO.md](docs/TODO.md) | Current tasks and progress |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decision log (DEC-XXX) |
| [docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md](docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md) | Complete architecture specification |
| [docs/DEPLOYMENT-SETUP.md](docs/DEPLOYMENT-SETUP.md) | Docker deployment guide |
| [docs/tasks/](docs/tasks/) | Detailed task specifications |
| [.github/instructions/](..github/instructions/) | Protocol documentation (agents reference these) |

---

## 🎓 Onboarding for Emre

If you're Emre joining the project, start here:

1. **Read this README** (you are here! ✅)
2. **Clone and run:** `git clone` → `docker compose up`
3. **Complete P1-E00:** [docs/tasks/P1-E00-codebase-onboarding.md](docs/tasks/P1-E00-codebase-onboarding.md)
4. **Read architecture:** [docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md](docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md)
5. **Learn protocols:** [.github/instructions/avaros-protocols.instructions.md](.github/instructions/avaros-protocols.instructions.md)

### Your First Tasks
- **P1-E00:** Codebase onboarding (explores structure, runs tests)
- **P1-E01:** Add unit tests (80%+ coverage)
- **P1-E02:** Turkish locale (tr-tr dialogs and intents)
- **P1-E03:** Docker dev environment improvements

**Note:** Work on feature branches, submit PRs for review. First-time approval = full story points! 🎯

---

## 🔐 Security & Compliance

- **GDPR-by-design:** Audit logs, RBAC, data minimization
- **TLS for all API calls**
- **No hardcoded credentials** - use SettingsService
- **Immutable audit trails** for recommendations

**See:** [docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md#security-compliance](docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md)

---

## 🗺️ Roadmap

### Phase 1: Deployment & Integration ✅
- [x] Deploy WASABI OVOS locally
- [x] AVAROS Docker integration
- [x] Skill loads in OVOS
- [x] End-to-end voice test
- [x] GitHub repository setup
- [ ] Emre onboarding tasks (P1-E00 to P1-E03)

### Phase 2: Intelligence Layer (Planned)
- [ ] DocuBoT integration (RAG for procedures/specs)
- [ ] PREVENTION service (anomaly detection)
- [ ] RENERYO adapter implementation
- [ ] Web UI (React dashboard)

### Phase 3: Production Hardening (Planned)
- [ ] Multi-platform adapters (SAP, Siemens)
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
- **Lead Developer:** [Your name/contact]
- **Junior Developer:** Emre - [GitHub: @EmresGitHubUsername]

---

## 📞 Support

For questions or issues:
- **Architecture:** Review [docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md](docs/AVAROS-ARCHITECTURE-IMPLEMENTATION-PLAN.md)
- **Tasks:** Check [docs/TODO.md](docs/TODO.md)
- **Decisions:** See [docs/DECISIONS.md](docs/DECISIONS.md)
- **Agents:** Use `@agent-name` in GitHub Copilot Chat

---

**Built with ❤️ for sustainable manufacturing**
