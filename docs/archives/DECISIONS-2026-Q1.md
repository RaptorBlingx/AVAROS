# Archived Decisions — 2026 Q1

> Archived from `docs/DECISIONS.md` on 2026-02-07
> These decisions are historical record. Active decisions remain in `docs/DECISIONS.md`.

---

## DEC-008: OVOS Deployment via WASABI Stack (2026-02-05) — ACTIVE (details archived)

**Context:** WASABI provides private Docker Compose for OVOS (expires 2027-01-31)
**Decision:** Use WASABI OVOS stack as base infrastructure, AVAROS installs as skill within it
**Rationale:** BIBA-maintained OVOS, battle-tested, deployment support included
**Consequences:**
- Must clone private GitLab repo (deployment token required)
- Responsible for retaining Docker images
- AVAROS skill deploys INTO OVOS container
- Updates managed by WASABI (notified via email)

---

## DEC-009: DocuBoT & PREVENTION are WASABI Components (2026-02-05) — PENDING (details archived)

**Context:** Reviewed WASABI proposal after searching WASABI OVOS repository (found no DocuBoT/PREVENTION)
**Decision:** DocuBoT and PREVENTION are **WASABI-stack components** that need to be requested from WASABI consortium
**Evidence from Proposal (Section 1.2):**
> "AVAROS adds three WASABI-stack components: OVOS for the conversational layer, DocuBoT to retrieve and ground answers in procedures, specifications and pilot documentation, and PREVENTION to support early detection of anomalies and risks in operations and supply flows."

**Clarification:**
- NOT in WASABI OVOS repository (confirmed by search)
- NOT part of RENERYO backend (separate platform)
- NOT services we build ourselves
- WASABI consortium provides them (need to request)

**Next Actions:**
1. Contact WASABI consortium: Request access to DocuBoT
2. Contact WASABI consortium: Request access to PREVENTION
3. Verify deployment token or separate access needed
4. Get Docker image names, API endpoints, configuration templates

---

## DEC-010: AVAROS Skill as Separate Docker Service (2026-02-05) — ACTIVE (details archived)

**Context:** WASABI README says "Additional skills should be connected via a separate container stack"
**Decision:** AVAROS deploys as separate Docker service that joins the `ovos` network
**Requirements:**
- Join `ovos` network
- Mount `ovos/config` from WASABI stack
- Mount `ovos/tmp` from WASABI stack
- Use same `mycroft.conf` as WASABI
**Implementation:** `docker/docker-compose.avaros.yml` references WASABI volumes

---

## DEC-011: WASABI OVOS Stack Deployed Successfully (2026-02-05) — COMPLETED

**Context:** P1-L01 completed - WASABI OVOS stack deployed and running on development server
**Details:**
- All containers running: ovos_core (healthy), ovos_messagebus, hivemind_listener, keycloak, nginx, dozzle
- Message bus service started successfully
- Hivemind client created: `avaros-client` (Node ID: 2)
- Credentials stored in `.hivemind-credentials` (gitignored)

**Deployment Command:**
```bash
cd /home/ubuntu/wasabi-ovos
docker compose -f docker-compose.hivemind.yml \
  -f docker-compose.ovos.base.yml \
  -f docker-compose.ovos.skills.yml \
  -f docker-compose.users.yml \
  -f docker-compose.utils.yml \
  -f docker-compose.yml up -d
```

---

## DEC-012: AVAROS Docker Integration Complete (2026-02-06) — COMPLETED

**Context:** P1-L02 completed - Created Docker Compose setup for AVAROS skill container
**Implementation:**
- `docker/docker-compose.avaros.yml` — Production Docker Compose configuration
- Updated `docker/Dockerfile` — Python 3.10 slim image with ovos user (uid 1000)
- Container mounts WASABI volumes: `ovos/config` (RO), `ovos/tmp` (RW)
- Container name: `avaros_skill`, Network: `ovos` (172.18.0.8/16)
- Health check verifies skill can be imported

**Bug Fixes Applied:**
1. Fixed syntax errors in `query_dispatcher.py` (literal `\n` and escaped quotes)
2. Fixed SQLAlchemy reserved word conflict: Renamed `metadata` column to `query_metadata` in `audit.py`

---

## DEC-013: AVAROS Skill Launcher Implementation (2026-02-06) — COMPLETED

**Context:** P1-L03 task - Skill container was running but not connecting to OVOS messagebus
**Decision:** Create custom launcher script (`launch_skill.py`) that properly initializes OVOSSkill with messagebus connection
**Implementation:**
- Created `launch_skill.py` — Connects to `ovos_messagebus:8181` and initializes AVAROSSkill
- Updated Dockerfile CMD to run launcher instead of placeholder
- Changed config volume mount from `:ro` to `:rw`

**Results:**
- Skill connects to messagebus, all 8 intents registered (94 templates)
- MockAdapter initializes correctly, skill reports "ready" status

---

## DEC-014: Skill Root Directory via _dir Attribute (2026-02-06) — ACTIVE (details archived)

**Context:** OVOS couldn't find intent files when skill deployed in custom directory
**Problem:** Setting `root_dir` after `super().__init__()` was too late (intents already loaded)
**Decision:** Set `self._dir` attribute BEFORE `super().__init__()` in skill `__init__` method
```python
def __init__(self, *args, **kwargs):
    from pathlib import Path
    self._dir = str(Path(__file__).parent)  # BEFORE super().__init__()
    super().__init__(*args, **kwargs)
```
**Known Issue (Non-Critical):** Skill container logs "Unable to find [intent].intent" warnings during init — does not affect functionality.

---

## DEC-015: E2E Testing via Message Bus (2026-02-06) — ACTIVE (details archived)

**Context:** Need to test end-to-end voice pipeline without physical microphone
**Decision:** Use OVOS message bus for E2E testing instead of voice input
**Implementation:** `test_e2e.py` sends `recognizer_loop:utterance` messages, listens for `speak` messages
**Results (P1-L04):** All 3 test intents passed, avg roundtrip 579ms (93.6% faster than 10s target)

---

## Superseded Decisions

### DEC-009 Original (DocuBoT Integration Strategy)
**Superseded by:** Finding that DocuBoT/PREVENTION not in WASABI stack
**Original Question:** Deployment method for DocuBoT

### DEC-010 Original (PREVENTION Integration)
**Superseded by:** Finding that PREVENTION not in WASABI stack
**Original Question:** Real-time vs batch for PREVENTION
