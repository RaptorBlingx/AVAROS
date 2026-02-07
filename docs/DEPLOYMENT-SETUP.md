# AVAROS Deployment Setup

**Last Updated:** February 5, 2026

---

## Infrastructure Overview

AVAROS consists of multiple components deployed via Docker Compose:

```
┌─────────────────────────────────────────┐
│  WASABI OVOS Stack (Base Layer)         │
│  https://gitlab.ips.biba.uni-bremen.de  │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ OVOS Core (Voice Assistant)     │   │
│  │ - Wake word detection           │   │
│  │ - Speech-to-Text                │   │
│  │ - Text-to-Speech                │   │
│  │ - Intent routing                │   │
│  └─────────────────────────────────┘   │
│           │                             │
│           ↓                             │
│  ┌─────────────────────────────────┐   │
│  │ AVAROS Skill (This Repo)        │   │  ← YOU BUILD THIS
│  │ - Manufacturing intents         │   │
│  │ - Query dispatcher              │   │
│  │ - Adapter pattern               │   │
│  │ - Web UI                        │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
           │
           ↓ HTTP/REST API calls
┌─────────────────────────────────────────┐
│  Backend Services                       │
│  ┌─────────────────────────────────┐   │
│  │ DocuBoT (RAG Service)           │   │  ← TODO: Clarify deployment
│  │ - ISO 50001 procedures          │   │
│  │ - Technical specs               │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │ PREVENTION (Anomaly Detection)  │   │  ← TODO: Clarify deployment
│  │ - Time series analysis          │   │
│  │ - Pattern detection             │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │ RENERYO/SAP (Data Platform)     │   │  ← Provided by manufacturer
│  │ - Energy KPIs                   │   │
│  │ - Material data                 │   │
│  │ - Production metrics            │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## Step 1: Deploy WASABI OVOS Stack

### 1.1 Clone Private Repository

**Deployment Details (Expires: January 31, 2027):**
```bash
# Clone the WASABI OVOS Docker Compose project
git clone https://deploy-token-avaros:<TOKEN>@gitlab.ips.biba.uni-bremen.de/rasa-assistant/tools-and-stacks/stacks/docker-compose-project-for-ovos wasabi-ovos

cd wasabi-ovos
```

**SECURITY:**
- ⚠️ **DO NOT commit deployment token** to this repository
- ⚠️ **DO NOT share token** outside AVAROS experiment
- Store token in password manager
- Token expires: January 31, 2027

### 1.2 Review License & README

```bash
# Read license restrictions
cat LICENSE

# Read deployment instructions
cat README.md
```

### 1.3 Deploy OVOS Base Stack

```bash
# Follow instructions in WASABI README
docker-compose up -d

# Verify OVOS is running
docker-compose ps
```

**Expected Services:**
- OVOS Core
- STT (Speech-to-Text) service
- TTS (Text-to-Speech) service
- Message bus
- Audio backend

---

## Step 2: Install AVAROS Skill (This Repository)

### 2.1 Clone AVAROS Repository

```bash
# Clone into OVOS skills directory (path from WASABI README)
cd /path/to/ovos/skills/  # Check WASABI README for exact path
git clone <avaros-repo-url> avaros-ovos-skill
cd avaros-ovos-skill
```

### 2.2 Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Or use Docker approach (Zero-Config)
docker-compose -f docker/docker-compose.skill.yml up -d
```

### 2.3 Configure Adapters

**First Run (Mock Mode - No Backend Required):**
```yaml
# skill/settings.yaml (auto-created)
adapter:
  type: mock
  name: "MockAdapter"
```

**Production (Connect to RENERYO):**
```yaml
# Configure via Web UI at http://localhost:8000/settings
adapter:
  type: reneryo
  api_url: "https://reneryo.example.com/api"
  api_key: "${RENERYO_API_KEY}"
```

---

## Step 3: Deploy Backend Services (TODO - Needs Clarification)

### 3.1 DocuBoT (RAG Service)

**Status:** ❓ Deployment method unknown

**Questions to Answer:**
- Is DocuBoT a separate Docker service?
- Is it part of RENERYO backend?
- Do we build it as part of AVAROS?
- What API endpoints does it expose?

**Mock for Phase 1:**
```python
# skill/services/docubot_mock.py
class DocuBotMock:
    def query(self, question: str) -> str:
        return "ISO 50001 procedure: [Mock response]"
```

### 3.2 PREVENTION (Anomaly Detection)

**Status:** ❓ Deployment method unknown

**Questions to Answer:**
- Is PREVENTION a separate service?
- Is it part of RENERYO?
- What ML models does it use?
- What API does it expose?

**Mock for Phase 1:**
```python
# skill/services/prevention_mock.py
class PreventionMock:
    def check_anomaly(self, metric: str, value: float) -> dict:
        return {"anomaly": False, "confidence": 0.95}
```

---

## Step 4: Integration Testing

### 4.1 Test OVOS Wake Word
```bash
# Say: "Hey Mycroft"
# Expected: Beep sound (wake word detected)
```

### 4.2 Test AVAROS Skill
```bash
# Say: "What's our energy per unit this week?"
# Expected: AVAROS responds with mock/real data
```

### 4.3 Check Logs
```bash
# OVOS logs
docker-compose -f wasabi-ovos/docker-compose.yml logs -f

# AVAROS skill logs
docker-compose -f avaros-ovos-skill/docker/docker-compose.skill.yml logs -f
```

---

## Maintenance & Updates

### Image Management
**You are responsible for:**
- Retaining copies of all OVOS Docker images
- Checking for updates from open-source maintainers
- Testing updates before deploying to production

```bash
# Backup current images
docker save ovos/ovos-core:latest -o ovos-core-backup.tar
docker save ovos/stt-service:latest -o stt-service-backup.tar

# Check for updates
docker-compose pull
docker-compose up -d
```

### WASABI Updates
- BIBA may update the Docker Compose project
- Updates will be announced via email
- Review changelog before applying updates

---

## Support Contacts

### OVOS Deployment Issues
**Contact:** BIBA team (via email from WASABI)  
**Available:** January 2026 for support telco  
**GitLab:** https://gitlab.ips.biba.uni-bremen.de

### AVAROS Skill Issues
**Repository:** This repo  
**Team:** Lead Developer + Emre

---

## TODO: Architecture Decisions Needed

**DEC-008: DocuBoT Deployment Strategy**
- [ ] Clarify if DocuBoT is separate service or RENERYO feature
- [ ] Document API contract
- [ ] Add deployment instructions

**DEC-009: PREVENTION Integration**
- [ ] Clarify PREVENTION deployment method
- [ ] Document anomaly detection API
- [ ] Decide: Real-time vs batch processing

**DEC-010: Service Discovery**
- [ ] How does AVAROS discover DocuBoT/PREVENTION?
- [ ] Environment variables? Service registry?
- [ ] Fallback behavior if services unavailable?

---

## Quick Start (Zero-Config Demo)

```bash
# 1. Deploy WASABI OVOS (one-time setup)
cd wasabi-ovos && docker-compose up -d

# 2. Start AVAROS with mock adapter
cd ../avaros-ovos-skill && docker-compose up

# 3. Say: "Hey Mycroft, what's our energy per unit?"
# 4. Should respond with mock data

# 5. Open Web UI: http://localhost:8000
```

**No configuration files to edit. No API keys needed for demo mode.**
