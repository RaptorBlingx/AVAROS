# AVAROS Developer Onboarding

> **Audience:** New developer joining AVAROS project
> **Goal:** Get both WASABI OVOS and AVAROS running and verified
> **Time:** 15 minutes
> **Outcome:** Ready to start your first task (P1-E01)

---

## Step 1: Verify SSH Access

```bash
ssh -T git@git.arti.ac
# Expected: "Hi <username>! You've been authenticated..."
# If this fails, ask Lead for SSH key setup.
```

---

## Step 2: Clone Both Repositories

### 2.1 Clone WASABI OVOS Stack

```bash
# Create a projects directory
mkdir -p ~/projects
cd ~/projects

# Clone WASABI OVOS (includes deployment token)
git clone https://deploy-token-avaros:gldt-dnQ-yHVwJcHLxk7LxTUq@gitlab.ips.biba.uni-bremen.de/rasa-assistant/tools-and-stacks/stacks/docker-compose-project-for-ovos wasabi-ovos

cd wasabi-ovos
```

**⚠️ Security Note:** The deployment token is embedded in this URL. DO NOT share this URL publicly or commit it to other repos.

### 2.2 Clone AVAROS Repository

```bash
# Return to projects directory
cd ~/projects

# Clone AVAROS via SSH
git clone ssh://git@git.arti.ac/europe/AVAROS.git avaros-ovos-skill
cd avaros-ovos-skill
```

**Your directory structure:**
```
~/projects/
├── wasabi-ovos/           # WASABI OVOS base stack
└── avaros-ovos-skill/     # AVAROS skill (this repo)
```

---

## Step 3: Start WASABI OVOS Stack

```bash
cd ~/projects/wasabi-ovos

# Start OVOS services
docker compose up -d

# Wait ~30 seconds for services to initialize

# Verify services are running
docker compose ps
```

**Expected services:**
- `ovos_core` (running)
- `ovos_messagebus` (running)
- `ovos_phal` (running)
- `ovos_audio` (running)

**Check logs:**
```bash
docker compose logs -f ovos_core
# Look for: "OVOS Core started successfully"
# Press Ctrl+C to exit logs
```

---

## Step 4: Start AVAROS Skill

```bash
cd ~/projects/avaros-ovos-skill

# Start AVAROS (connects to WASABI OVOS network)
docker compose -f docker/docker-compose.avaros.yml up --build -d

# Check AVAROS logs
docker compose -f docker/docker-compose.avaros.yml logs -f
```

**Look for these success messages:**
1. `"AVAROS skill initialized with adapter: MockAdapter"`
2. `"Connected to OVOS messagebus"`
3. `"Registered 8 intent handlers"`

**Press Ctrl+C to exit logs.**

---

## Step 5: Verify Everything Works

### 5.1 Check Running Containers

```bash
# From any directory
docker ps
```

You should see:
- **WASABI OVOS containers** (4-5 containers)
- **avaros_skill container** (1 container)

All should show status: `Up` or `healthy`

### 5.2 Test AVAROS Intent Registration

```bash
# Check AVAROS registered intents
cd ~/projects/avaros-ovos-skill
docker compose -f docker/docker-compose.avaros.yml logs | grep "Registered intent"
```

**Expected output:** Should list ~8 intents like:
- `avaros.kpi.intent`
- `avaros.comparison.intent`
- `avaros.trend.intent`
- etc.

---

## Step 6: Explore the AVAROS Codebase

Now that everything is running, explore the project structure:

### 6.1 Project Structure

### 6.1 Project Structure

```
avaros-ovos-skill/
├── skill/                        # Production code (OVOS skill)
│   ├── __init__.py               # Main skill — 8 intent handlers (290 lines)
│   ├── domain/                   # Business logic (platform-agnostic)
│   │   ├── models.py             # CanonicalMetric (19 metrics), DataPoint, Anomaly
│   │   ├── results.py            # 5 result types (KPIResult, TrendResult, etc.)
│   │   └── exceptions.py         # AVAROSError hierarchy
│   ├── adapters/                 # Backend connectors
│   │   ├── base.py               # ManufacturingAdapter interface (ABC)
│   │   ├── mock.py               # MockAdapter — demo data (245 lines)
│   │   └── factory.py            # Selects adapter from settings
│   ├── use_cases/
│   │   └── query_dispatcher.py   # Routes queries, adds intelligence (421 lines)
│   └── services/
│       ├── settings.py           # Config management (187 lines)
│       ├── audit.py              # GDPR audit trails (206 lines)
│       └── response_builder.py   # Voice formatting (303 lines)
├── tests/                        # Test suite (120 tests, all passing)
│   ├── test_domain/              # Domain layer tests
│   ├── test_exceptions.py        # Exception tests (579 lines)
│   └── test_result_types.py      # Result type tests (720 lines)
├── docker/                       # Docker configuration
│   ├── Dockerfile
│   └── docker-compose.avaros.yml # WASABI integration
└── docs/                         # Documentation
    ├── DEVELOPMENT.md            # Coding standards (1,316 lines)
    ├── TODO.md                   # Active task tracker
    └── tasks/                    # Your task specs
```

### 6.2 Key Files to Read

**Start here (read in this order):**

1. **`docs/TODO.md`** — Your task list and current phase status
2. **`skill/domain/models.py`** (lines 1-100) — Understand `CanonicalMetric` enum
3. **`skill/adapters/base.py`** — The ManufacturingAdapter interface
4. **`skill/adapters/mock.py`** — See how MockAdapter implements the interface
5. **`skill/__init__.py`** (lines 1-100) — Intent handler structure

**Don't read everything at once.** Read files as you need them for your tasks.

### 6.3 Key Concepts

| Concept | What It Is | Why It Matters |
|---------|-----------|----------------|
| **CanonicalMetric** | 19 universal manufacturing metrics (energy_per_unit, oee, scrap_rate, co2_total, etc.) | Platform-agnostic design — never use platform-specific names |
| **ManufacturingAdapter** | Abstract interface (ABC) for backend systems | All platforms (RENERYO, SAP, Siemens) implement this |
| **MockAdapter** | Demo adapter with fake data | Zero-config: works immediately, no API credentials needed |
| **QueryDispatcher** | Routes queries to adapters, adds intelligence | Orchestration layer — adapters are dumb, dispatcher is smart |
| **ResponseBuilder** | Formats results for voice output | Converts KPIResult → natural speech |

---

## Step 7: Understand the Architecture

### 7.1 The 7 Architecture Rules (DEC-001 to DEC-007)

These are **non-negotiable**. Read `DEVELOPMENT.md` lines 18-251 for details.

| Rule | Quick Summary |
|------|--------------|
| **DEC-001** Platform-Agnostic | Never use platform names (reneryo, sap) in domain/handlers |
| **DEC-002** Universal Metrics | Always use `CanonicalMetric`, never strings like "seu" |
| **DEC-003** Clean Architecture | Domain NEVER imports infrastructure layers |
| **DEC-004** Immutable Models | All domain dataclasses use `frozen=True` |
| **DEC-005** Zero-Config | Must work without config files (MockAdapter fallback) |
| **DEC-006** Settings Service | Credentials via SettingsService, never hardcoded |
| **DEC-007** Smart Orchestration | Adapters fetch data; intelligence in QueryDispatcher |

### 7.2 Layer Separation

```
┌─────────────────────────────────┐
│  skill/__init__.py              │  ← Intent handlers (Voice UI)
│  (8 handlers)                   │
└───────────┬─────────────────────┘
            │
            ↓
┌─────────────────────────────────┐
│  use_cases/query_dispatcher.py  │  ← Orchestration layer
│  (Routes queries, adds logic)   │
└───────────┬─────────────────────┘
            │
            ↓
┌─────────────────────────────────┐
│  adapters/                       │  ← Data access layer
│  (MockAdapter, future: RENERYO) │
└───────────┬─────────────────────┘
            │
            ↓
┌─────────────────────────────────┐
│  domain/                         │  ← Business logic (platform-agnostic)
│  (models, results, exceptions)  │
└─────────────────────────────────┘
```

**Rule:** Dependencies point DOWNWARD only. Domain knows nothing about adapters or handlers.

---

## Step 8: Stop the Stacks (When Done)

```bash
# Stop AVAROS
cd ~/projects/avaros-ovos-skill
docker compose -f docker/docker-compose.avaros.yml down

# Stop WASABI OVOS
cd ~/projects/wasabi-ovos
docker compose down
```

---

## Next Steps: Your First Task

**Congratulations!** You've completed onboarding. Both stacks are running, you understand the structure.

### Your First Development Task

**Task:** P1-E01 (details in `docs/tasks/P1-E01-*.md`)

**Before starting P1-E01:**
- Read the task spec in `docs/tasks/`
- Create a feature branch: `git checkout -b feature/emre-P1-E01-<task-name>`
- Read relevant sections of `DEVELOPMENT.md` as needed (don't read all 1,316 lines!)

---

## Getting Help

| Question | Where to Look |
|----------|--------------|
| **Docker not working?** | Ask Lead (Mohamad) |
| **Architecture question?** | Read `DEVELOPMENT.md` (use grep/search) |
| **Task unclear?** | Check `docs/tasks/` spec first, then ask Lead |
| **Found a bug?** | Note it, discuss with Lead |

---

## Reference Commands

```bash
# View all running containers
docker ps

# Check AVAROS logs
cd ~/projects/avaros-ovos-skill
docker compose -f docker/docker-compose.avaros.yml logs -f

# Check WASABI OVOS logs
cd ~/projects/wasabi-ovos
docker compose logs -f ovos_core

# Restart AVAROS (after code changes)
cd ~/projects/avaros-ovos-skill
docker compose -f docker/docker-compose.avaros.yml restart

# Rebuild AVAROS (after dependency changes)
docker compose -f docker/docker-compose.avaros.yml up --build -d
```
