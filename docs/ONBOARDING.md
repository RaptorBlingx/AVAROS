# AVAROS Developer Onboarding

> **Audience:** New developer (Emre)
> **Goal:** Get AVAROS running with zero configuration
> **Time:** 10 minutes

---

## Quick Start (Zero-Config)

### 1. Verify SSH Access

```bash
ssh -T git@git.arti.ac
# Expected: "Hi <username>! You've been authenticated..."
# If this fails, ask Lead for SSH key setup.
```

### 2. Clone & Run

```bash
# Clone the repository
git clone ssh://git@git.arti.ac/europe/AVAROS.git avaros-ovos-skill
cd avaros-ovos-skill

# Start AVAROS with Docker (standalone mode)
docker compose up --build

# That's it! AVAROS is running.
# Check logs for: "AVAROS skill initialized with adapter: MockAdapter"
```

**What just happened?**
- Docker built the AVAROS container with all dependencies
- MockAdapter provides demo data (no configuration needed)
- OVOS core is bundled — fully functional voice assistant
- Web UI available at http://localhost:5000 (coming in Phase 2)

**Stop everything:**
```bash
docker compose down
```

---

## Developer Setup (For Writing Code)

### 1. Project Structure

```
avaros-ovos-skill/
├── skill/                        # Production code (OVOS skill)
│   ├── __init__.py               # Main skill — 8 intent handlers
│   ├── domain/                   # Business logic (platform-agnostic)
│   │   ├── models.py             # CanonicalMetric, DataPoint, Anomaly
│   │   ├── results.py            # KPIResult, TrendResult, ComparisonResult
│   │   └── exceptions.py         # AVAROSError hierarchy
│   ├── adapters/                 # Backend connectors
│   │   ├── base.py               # ManufacturingAdapter interface
│   │   ├── mock.py               # MockAdapter (demo data)
│   │   └── factory.py            # Selects adapter from config
│   ├── use_cases/                # Orchestration layer
│   │   └── query_dispatcher.py   # Routes queries, adds intelligence
│   └── services/                 # Support services
│       ├── settings.py           # Configuration management
│       ├── audit.py              # GDPR audit trails
│       └── response_builder.py   # Voice-optimized responses
├── tests/                        # Test suite (120 tests, all passing)
├── docker/                       # Docker files
└── docs/                         # Documentation
```

### 2. Install Dependencies (Local Development)

```bash
# Create virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies (includes pytest)
pip install -r requirements.txt
```

### 3. Run Tests

```bash
# Run full test suite
pytest tests/ -v

# Expected: 120 passed in ~1s
```

All tests already written and passing. Available test files:
- `tests/test_domain/test_models.py` (567 lines)
- `tests/test_exceptions.py` (579 lines)  
- `tests/test_result_types.py` (720 lines)

### 4. Connect to WASABI OVOS Stack (Advanced)

For development with the full WASABI OVOS deployment:

```bash
# Prerequisite: WASABI OVOS stack must be running
# Location: ../wasabi-ovos/ (sibling directory)
# Ask Lead for deploy token if you need to set up WASABI

# Start AVAROS in WASABI mode
docker compose -f docker/docker-compose.avaros.yml up --build

# Check logs
docker compose -f docker/docker-compose.avaros.yml logs -f
```

---

## Key Concepts

| Concept | File | What It Does |
|---------|------|-------------|
| **CanonicalMetric** | `skill/domain/models.py` | 19 universal manufacturing metrics (energy_per_unit, oee, scrap_rate, etc.) |
| **QueryDispatcher** | `skill/use_cases/query_dispatcher.py` | Routes voice queries to adapters, adds intelligence |
| **ManufacturingAdapter** | `skill/adapters/base.py` | Abstract interface — all backends implement this |
| **MockAdapter** | `skill/adapters/mock.py` | Demo adapter with fake data — works with zero config |
| **ResponseBuilder** | `skill/services/response_builder.py` | Formats results into natural voice responses |

---

## Coding Standards (Quick Reference)

**Full standards:** Read `DEVELOPMENT.md` on demand (1,316 lines)

### Architecture Rules (DEC-001–007)

| Rule | What It Means |
|------|--------------|
| **DEC-001** Platform-Agnostic | Never use platform names (reneryo, sap) in domain/handlers |
| **DEC-002** Universal Metrics | Always use `CanonicalMetric` enum, never strings |
| **DEC-003** Clean Architecture | Domain NEVER imports infrastructure layers |
| **DEC-004** Immutable Models | All domain dataclasses use `frozen=True` |
| **DEC-005** Zero-Config | Must work without config files (MockAdapter fallback) |
| **DEC-006** Settings Service | All credentials via SettingsService, never hardcoded |
| **DEC-007** Smart Orchestration | Adapters fetch data; intelligence in QueryDispatcher |

### Test Standards

```python
# Naming: test_{function}_{scenario}_{expected}
def test_creation_with_valid_metric_creates_result():
    pass

# AAA pattern
def test_to_dict_serializes_correctly():
    # Arrange
    result = KPIResult(metric=CanonicalMetric.OEE, value=82.5, ...)
    
    # Act
    result_dict = result.to_dict()
    
    # Assert
    assert result_dict["metric"] == "oee"

# Always import production code
from skill.domain.results import KPIResult
from skill.domain.exceptions import AVAROSError
```

### Code Quality

- Type hints on all parameters and returns
- Max 20 lines per function
- Max 300 lines per file
- Docstrings on public functions (Args, Returns, Raises)
- No bare `except:` — catch specific exceptions

### Git Workflow

```bash
# Branch naming
git checkout -b feature/emre-P1-E01-onboarding

# Commit format
git commit -m "feat(tests): add adapter unit tests"
git commit -m "docs(onboarding): add notes from P1-E01"

# Push and create PR on Forgejo
git push origin feature/emre-P1-E01-onboarding
```

---

## Your First Task: P1-E01

**Full spec:** `docs/tasks/P1-E01-codebase-onboarding.md`

**Summary:**
1. Clone and run (you already did this!)
2. Run tests locally — verify 120/120 pass
3. Read through the codebase — understand layer separation
4. Write a short `docs/P1-E01-onboarding-notes.md` with questions/issues
5. No production code changes — read/verify only

---

## Getting Help

- **Docker/networking issues?** → Ask Lead (Mohamad)
- **Architecture questions?** → Read specific section in `DEVELOPMENT.md`
- **Task unclear?** → Check `docs/tasks/` spec first, then ask Lead
- **Found a bug/doc issue?** → Write it in your onboarding notes
