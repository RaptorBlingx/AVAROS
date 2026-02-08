# AVAROS Developer Onboarding

> **Audience:** New developer (Emre)
> **Prerequisites:** Git, Docker & Docker Compose, Python 3.10+, SSH access to Forgejo
> **Time to complete:** ~1 hour

---

## 1. Verify SSH Access

Before cloning, confirm your SSH key is registered on Forgejo:

```bash
ssh -T git@git.arti.ac
# Expected: "Hi <username>! You've been authenticated..."
# If this fails, ask Lead for SSH key setup help.
```

---

## 2. Clone the Repository

```bash
# Clone via SSH
git clone ssh://git@git.arti.ac/europe/AVAROS.git avaros-ovos-skill
cd avaros-ovos-skill

# Verify you're on the main branch
git branch
# Expected output: * main
```

---

## 3. Project Structure Overview

```
avaros-ovos-skill/
├── skill/                        # OVOS skill (production code)
│   ├── __init__.py               # Main skill class — 8 intent handlers
│   ├── domain/                   # Business logic (platform-agnostic)
│   │   ├── models.py             # CanonicalMetric enum, DataPoint, Anomaly, etc.
│   │   ├── results.py            # KPIResult, TrendResult, ComparisonResult, etc.
│   │   └── exceptions.py         # AVAROSError hierarchy
│   ├── adapters/                 # Backend connectors
│   │   ├── base.py               # ManufacturingAdapter (abstract interface)
│   │   ├── mock.py               # MockAdapter — demo data, works out-of-the-box
│   │   └── factory.py            # Creates the right adapter from config
│   ├── use_cases/
│   │   └── query_dispatcher.py   # Routes queries, adds intelligence (DEC-007)
│   ├── services/
│   │   ├── settings.py           # Configuration management
│   │   ├── audit.py              # GDPR audit trails
│   │   └── response_builder.py   # Formats results for voice output
│   └── locale/en-us/             # Intent files and dialog templates
├── tests/                        # Test suite (pytest)
│   ├── test_domain/test_models.py
│   ├── test_exceptions.py
│   ├── test_result_types.py
│   └── conftest.py               # Shared fixtures
├── docker/                       # Docker artifacts
│   ├── Dockerfile
│   └── docker-compose.avaros.yml # WASABI integration compose file
├── docker-compose.yml            # Standalone mode (bundled ovos-core)
├── launch_skill.py               # Skill entry point for Docker
├── requirements.txt              # Python dependencies
├── DEVELOPMENT.md                # Coding standards (read on demand)
└── docs/                         # Documentation
    ├── TODO.md                   # Active task tracker
    ├── DECISIONS.md              # Architecture decisions (DEC-XXX)
    └── tasks/                    # Your task specs live here
```

**Key concepts to understand:**

| Concept | File | What It Does |
|---------|------|-------------|
| `CanonicalMetric` | `skill/domain/models.py` | Enum of 19 universal manufacturing metrics (energy_per_unit, oee, scrap_rate, etc.) |
| `QueryDispatcher` | `skill/use_cases/query_dispatcher.py` | Routes voice queries to the right adapter method, adds intelligence |
| `ManufacturingAdapter` | `skill/adapters/base.py` | Abstract interface — all backends implement this |
| `MockAdapter` | `skill/adapters/mock.py` | Demo adapter with fake data — works with zero configuration |
| `ResponseBuilder` | `skill/services/response_builder.py` | Formats KPI results into natural-sounding voice responses |

---

## 4. Install Python Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install production dependencies
pip install -r requirements.txt

# Install test dependencies
pip install -r tests/requirements-test.txt
```

---

## 5. Run Tests

This is the fastest way to verify everything works:

```bash
# Run full test suite
python3 -m pytest tests/ -v

# Expected output:
# 120 passed, 0 failures
```

If all 120 tests pass, your environment is set up correctly.

### Run specific test groups

```bash
# Domain model tests only
python3 -m pytest tests/test_domain/ -v

# Exception tests only
python3 -m pytest tests/test_exceptions.py -v

# Result type tests only
python3 -m pytest tests/test_result_types.py -v
```

---

## 6. Run with Docker (Standalone Mode)

Standalone mode bundles its own OVOS core — no WASABI stack needed:

```bash
# Build and start
docker compose up --build -d

# Check containers are running
docker compose ps
# Expected: avaros-skill (healthy), avaros-ovos-core (running)

# View AVAROS logs
docker compose logs -f avaros
# Look for: "AVAROS skill initialized with adapter: MockAdapter"

# Stop everything
docker compose down
```

---

## 7. Run with WASABI OVOS Stack (Development Mode)

This connects AVAROS to the full WASABI OVOS deployment. You need the WASABI stack running first.

### 7.1 Set Up WASABI OVOS (one-time)

```bash
# Go to your projects directory (sibling of avaros-ovos-skill)
cd ..

# Clone the WASABI OVOS stack (ask Lead for the deploy token)
git clone https://deploy-token-avaros:<TOKEN>@gitlab.ips.biba.uni-bremen.de/rasa-assistant/tools-and-stacks/stacks/docker-compose-project-for-ovos wasabi-ovos

cd wasabi-ovos
docker compose up -d

# Verify OVOS services are running
docker compose ps
# Expected: ovos-core, messagebus, STT, TTS services
```

> **Important:** The deploy token is sensitive. Do NOT commit it anywhere. Ask Lead if you don't have it.

### 7.2 Start AVAROS in WASABI Mode

```bash
# Back to AVAROS directory
cd ../avaros-ovos-skill

# Start AVAROS, joining the WASABI OVOS network
docker compose -f docker/docker-compose.avaros.yml up --build -d

# Check logs
docker compose -f docker/docker-compose.avaros.yml logs -f
# Look for: "AVAROS skill initialized with adapter: MockAdapter"
```

### Expected Directory Layout

```
~/projects/                     # (or wherever you keep repos)
├── wasabi-ovos/                # WASABI OVOS Docker stack
│   └── ovos/config/            # OVOS config (shared with AVAROS)
└── avaros-ovos-skill/          # This repo
    └── docker/
        └── docker-compose.avaros.yml  # References ../wasabi-ovos
```

---

## 8. Coding Standards (Quick Reference)

Full standards are in `DEVELOPMENT.md`. Here are the essentials:

### Architecture Rules (DEC-001–007)

| Rule | What It Means |
|------|--------------|
| **DEC-001 Platform-Agnostic** | Never use platform names (reneryo, sap) in domain code or handlers |
| **DEC-002 Universal Metrics** | Always use `CanonicalMetric` enum — never raw strings like "seu" |
| **DEC-003 Clean Architecture** | Domain layer NEVER imports from infrastructure layers |
| **DEC-004 Immutable Models** | All domain dataclasses use `frozen=True` |
| **DEC-005 Zero-Config** | Must work without config files (MockAdapter fallback) |
| **DEC-006 Settings Service** | All credentials via SettingsService — never hardcoded |
| **DEC-007 Smart Orchestration** | Adapters only fetch data; intelligence lives in QueryDispatcher |

### Test Standards

```python
# Naming: test_{function}_{scenario}_{expected}
def test_creation_with_valid_metric_creates_result():

# AAA pattern: Arrange → Act → Assert
def test_to_dict_with_all_fields_serializes_correctly():
    # Arrange
    result = KPIResult(metric=CanonicalMetric.OEE, value=82.5, ...)

    # Act
    result_dict = result.to_dict()

    # Assert
    assert result_dict["metric"] == "oee"

# Always import from production code — never redefine classes locally
from skill.domain.results import KPIResult
from skill.domain.exceptions import AVAROSError
```

### Code Quality

- Type hints on every parameter and return value
- Max 20 lines per function — extract helpers
- Max 300 lines per file
- Docstrings on all public functions (Args, Returns, Raises)
- No bare `except:` — always catch specific exceptions

### Git Workflow

```bash
# Branch naming
git checkout -b feature/emre-P1-E01-onboarding

# Commit format: <type>(<scope>): <subject>
git commit -m "feat(tests): add domain result type unit tests"
git commit -m "docs(onboarding): add setup notes from P1-E01"

# Push and create PR
git push origin feature/emre-P1-E01-onboarding
# Then create a Pull Request on Forgejo
```

---

## 9. Your First Task

Your first AVAROS task is **P1-E01: Codebase Onboarding** (2 pts).

Full spec: `docs/tasks/P1-E01-codebase-onboarding.md`

**Summary:**
1. Follow this onboarding doc (you're reading it now)
2. Run tests — confirm 120/120 pass
3. Read through the codebase — understand the layer separation
4. Write a short `docs/P1-E01-onboarding-notes.md` with any questions or issues
5. No production code changes — this is read/verify only

**After P1-E01**, your next task is **P1-E02: Write unit tests for domain result types** (3 pts). Spec in `docs/tasks/P1-E02-domain-results-tests.md`.

---

## 10. Getting Help

- **Stuck on Docker/networking?** → Ask Lead (Mohamad)
- **Architecture question?** → Read `DEVELOPMENT.md` section index in `.github/copilot-instructions.md`
- **Task unclear?** → Check your task spec in `docs/tasks/` first, then ask Lead
- **Found a bug or doc issue?** → Write it in your onboarding notes — that's valuable feedback
