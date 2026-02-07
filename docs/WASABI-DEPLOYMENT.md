# AVAROS + WASABI OVOS - Complete Deployment Guide

**Last Updated:** February 5, 2026  
**Repository Cloned:** ✅ `/home/ubuntu/wasabi-ovos`

---

## 📋 What We Have Now

### ✅ WASABI OVOS Stack (Cloned Successfully)
**Location:** `/home/ubuntu/wasabi-ovos`  
**Components:**
- OVOS Core (message bus, STT, TTS)
- Hivemind (secure device connections)
- Keycloak (identity management)
- Nginx (reverse proxy)
- Default fallback skill

**Key Finding:** 
- ❌ **No DocuBoT** mentioned in WASABI stack
- ❌ **No PREVENTION** mentioned in WASABI stack
- ✅ **Clear instructions** for adding custom skills

### 🔨 AVAROS Skill (This Repository)
**Location:** `/home/ubuntu/avaros-ovos-skill`  
**Status:** Development in progress  
**Deployment Method:** Separate Docker container that joins `ovos` network

---

## 🏗️ Architecture Understanding

```
┌─────────────────────────────────────────────┐
│  WASABI OVOS Stack                          │
│  (/home/ubuntu/wasabi-ovos/)                │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │ OVOS Core + Message Bus               │ │
│  │ - Network: ovos                       │ │
│  │ - Volumes: ovos/config, ovos/tmp      │ │
│  └───────────────────────────────────────┘ │
│  ┌───────────────────────────────────────┐ │
│  │ Default Skills                        │ │
│  │ - Fallback Unknown Skill              │ │
│  └───────────────────────────────────────┘ │
│  ┌───────────────────────────────────────┐ │
│  │ Hivemind + Keycloak + Nginx           │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                    ↑
                    │ Joins ovos network
                    │ Mounts shared volumes
                    │
┌─────────────────────────────────────────────┐
│  AVAROS Skill (Separate Container)         │
│  (/home/ubuntu/avaros-ovos-skill/)          │
│                                             │
│  - Joins: ovos network                      │
│  - Mounts: ../wasabi-ovos/ovos/config       │
│  - Mounts: ../wasabi-ovos/ovos/tmp          │
│  - Uses: same mycroft.conf                  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Backend Services (External)                │
│  - RENERYO/SAP (data platform)              │
│  - DocuBoT (❓ part of RENERYO?)            │
│  - PREVENTION (❓ part of RENERYO?)         │
└─────────────────────────────────────────────┘
```

---

## 🚀 Deployment Steps

### Step 1: Prepare WASABI OVOS Stack

#### 1.1 Navigate to WASABI Directory
```bash
cd /home/ubuntu/wasabi-ovos
```

#### 1.2 Create Environment Files
```bash
# Copy all .sample files
for f in $(find . -name "*.sample"); do 
  cp "$f" "${f%.sample}"
done

# Verify files created
ls -la .env
ls -la ovos/.shared.env
```

#### 1.3 Configure Environment Variables
```bash
# Edit main .env file
nano .env

# Key variables (from README):
COMPOSE_PROJECT_NAME=wasabi-base
VERSION=stable
OVOS_CONFIG_FOLDER=./ovos/config
OVOS_SHARE_FOLDER=./ovos/share
OVOS_TMP_FOLDER=./ovos/tmp
OVOS_USER=ovos
PULL_POLICY=always
```

#### 1.4 Create Docker Network
```bash
docker network create ovos
```

#### 1.5 Pull Images
```bash
docker compose \
  -f docker-compose.hivemind.yml \
  -f docker-compose.ovos.base.yml \
  -f docker-compose.ovos.skills.yml \
  -f docker-compose.users.yml \
  -f docker-compose.utils.yml \
  -f docker-compose.yml \
  pull --ignore-pull-failures
```

#### 1.6 Start WASABI Stack
```bash
docker compose \
  -f docker-compose.hivemind.yml \
  -f docker-compose.ovos.base.yml \
  -f docker-compose.ovos.skills.yml \
  -f docker-compose.users.yml \
  -f docker-compose.utils.yml \
  -f docker-compose.yml \
  up -d
```

#### 1.7 Configure Hivemind Client
```bash
# Add client for AVAROS (or COALA App)
docker exec --interactive --tty hivemind_listener \
  hivemind-core add-client \
  --name avaros-client \
  --access-key $(openssl rand -hex 16) \
  --password $(openssl rand -base64 12)

# List clients to verify
docker exec --interactive --tty hivemind_listener \
  hivemind-core list-clients
```

#### 1.8 Verify OVOS is Running
```bash
# Check all containers
docker compose \
  -f docker-compose.hivemind.yml \
  -f docker-compose.ovos.base.yml \
  -f docker-compose.ovos.skills.yml \
  -f docker-compose.users.yml \
  -f docker-compose.utils.yml \
  -f docker-compose.yml \
  ps

# Check logs
docker logs ovos_core
docker logs ovos_messagebus

# Access Dozzle (log viewer)
# Open: http://localhost:8888
```

---

### Step 2: Deploy AVAROS Skill

#### 2.1 Navigate to AVAROS Directory
```bash
cd /home/ubuntu/avaros-ovos-skill
```

#### 2.2 Create AVAROS Docker Compose File
```bash
# Create deployment config
cat > docker/docker-compose.avaros.yml <<'EOF'
version: '3.8'

services:
  avaros_skill:
    container_name: avaros_skill
    hostname: avaros_skill
    restart: unless-stopped
    build:
      context: ..
      dockerfile: docker/Dockerfile
    networks:
      - ovos
    volumes:
      # Mount WASABI OVOS shared config
      - ../wasabi-ovos/ovos/config:/home/ovos/.config/mycroft:ro
      - ../wasabi-ovos/ovos/tmp:/tmp/mycroft
      # Mount AVAROS skill code
      - ../skill:/opt/avaros/skill:ro
      - ./logs:/opt/avaros/logs
    environment:
      - ADAPTER_TYPE=mock
      - LOG_LEVEL=INFO
    depends_on:
      - ovos_messagebus

networks:
  ovos:
    external: true
EOF
```

#### 2.3 Create Dockerfile for AVAROS
```bash
cat > docker/Dockerfile <<'EOF'
FROM python:3.10-slim

WORKDIR /opt/avaros

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy skill code
COPY skill/ ./skill/

# Create ovos user
RUN useradd -m -u 1000 ovos && \
    chown -R ovos:ovos /opt/avaros

USER ovos

CMD ["python", "-m", "skill"]
EOF
```

#### 2.4 Build and Start AVAROS Skill
```bash
cd docker
docker compose -f docker-compose.avaros.yml build
docker compose -f docker-compose.avaros.yml up -d
```

#### 2.5 Verify AVAROS is Connected
```bash
# Check logs
docker logs avaros_skill

# Should see:
# - Connected to OVOS message bus
# - Skill registered
# - Intent handlers loaded
```

---

### Step 3: Test End-to-End

#### 3.1 Test OVOS Wake Word
```bash
# Say: "Hey Mycroft"
# Expected: Beep sound (wake word detected)
```

#### 3.2 Test AVAROS Skill
```bash
# Say: "What's our energy per unit this week?"
# Expected: AVAROS responds with mock data
```

#### 3.3 Check Message Bus Communication
```bash
# Monitor OVOS message bus
docker logs -f ovos_messagebus

# Should see:
# - Intent recognized: kpi.energy.per_unit
# - Skill response generated
```

---

## 🔍 What We Learned from WASABI Stack

### Comprehensive Search Results ✅

**Files Searched:**
- All docker-compose files (8 files)
- README.md
- All configuration files (.env, .json, .conf)
- Keycloak realm configuration
- License file

**Search Terms Used:**
- "docubot", "docu", "DocuBoT"
- "prevention", "PREVENTION"  
- "avaros", "AVAROS", "reneryo", "RENERYO"
- "rag", "anomaly"

**Result:** ❌ **ZERO MATCHES**

### What IS in WASABI Stack:

**Core Services:**
1. **OVOS Core** - `docker.io/smartgic/ovos-core:stable`
2. **OVOS Message Bus** - `docker.io/smartgic/ovos-messagebus:stable`
3. **Hivemind Listener** - `docker.io/smartgic/hivemind-listener:alpha`
4. **Keycloak** - `quay.io/keycloak/keycloak:23.0.4` (identity management)
5. **Keycloak DB** - `mysql:8`
6. **Nginx** - `nginx:latest` (reverse proxy)
7. **Dozzle** - `amir20/dozzle:latest` (log viewer)
8. **OVOS Fallback Skill** - `docker.io/smartgic/ovos-skill-fallback-unknown:stable`

### What is NOT in WASABI Stack:

❌ **DocuBoT** - No mention anywhere  
❌ **PREVENTION** - No mention anywhere  
❌ **RENERYO** - No mention anywhere  
❌ **AVAROS** - Only the deployment token name references it  
❌ **Any manufacturing-specific services**

### Confirmed Understanding:

1. **WASABI provides ONLY the OVOS infrastructure**
   - Voice assistant framework
   - User management (Keycloak)
   - Reverse proxy (Nginx)
   - Basic monitoring (Dozzle)

2. **DocuBoT & PREVENTION are external services**
   - Not part of WASABI/OVOS stack
   - **Must be part of RENERYO backend OR separate services**
   - Need to clarify with manager

3. **AVAROS is a custom skill**
   - Deploys as separate container
   - Joins `ovos` network
   - Mounts shared OVOS config

---

## ✅ CORRECTED ARCHITECTURE (From Proposal)

### The Full Stack:

```
┌─────────────────────────────────────────────────────────────┐
│                    AVAROS Docker-Compose Stack              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                          │
│  │ WASABI OVOS  │ ← Voice/Text Interface                   │
│  │ (from GitLab)│                                           │
│  └──────┬───────┘                                           │
│         │                                                   │
│         ↓                                                   │
│  ┌──────────────┐                                          │
│  │ AVAROS Skill │ ← Our Custom OVOS Skill                  │
│  └──┬────────┬──┘                                           │
│     │        │                                              │
│     ↓        ↓                                              │
│  ┌──────┐ ┌───────────┐                                    │
│  │DocuBoT│ │PREVENTION │ ← WASABI Stack Components         │
│  │(RAG)  │ │(Anomaly)  │    (Need to request from WASABI)  │
│  └───┬───┘ └─────┬─────┘                                    │
│      │           │                                          │
│      └─────┬─────┘                                          │
│            ↓                                                │
│     ┌──────────────┐                                        │
│     │   RENERYO    │ ← ArtiBilim's Data Platform           │
│     │  (REST API)  │   (Manufacturing data, supplier data)  │
│     └──────┬───────┘                                        │
│            │                                                │
└────────────┼────────────────────────────────────────────────┘
             │
             ↓
      ┌─────────────┐
      │ ERP/MES/IoT │ ← Factory Systems
      └─────────────┘
```

### Component Ownership:

1. **WASABI OVOS** (from GitLab) ✅
   - OVOS Core, Message Bus, Hivemind
   - Keycloak, Nginx, Dozzle
   - Status: Already cloned

2. **DocuBoT** (WASABI component) ❓
   - RAG service for document grounding
   - **Source:** WASABI consortium (need to request)
   - **NOT** in WASABI OVOS repository
   - **NOT** part of RENERYO

3. **PREVENTION** (WASABI component) ❓
   - Anomaly/drift detection service
   - **Source:** WASABI consortium (need to request)
   - **NOT** in WASABI OVOS repository
   - **NOT** part of RENERYO

4. **AVAROS Skill** (our code) 🔨
   - Custom OVOS skill
   - Status: In development

5. **RENERYO** (ArtiBilim platform) 🏭
   - Manufacturing data backend
   - Separate from WASABI components

---

## ❓ Questions for WASABI Consortium (UPDATED)

### About DocuBoT & PREVENTION:

**From Section 1.4 of proposal:**
> "DocuBoT (retrieval grounding): We will request setup and configuration guidance to confirm the indexing pipeline and grounding patterns..."
>
> "PREVENTION (anomaly/drift): We will request integration guidance focused on data schemas and API endpoints..."

**Questions:**

1. **How do we access DocuBoT and PREVENTION?**
   - Are they in a separate GitLab repository?
   - Do we use the same deployment token?
   - Are they Docker images we pull?

2. **DocuBoT Setup:**
   - What is the Docker image name/tag?
   - How do we configure the indexing pipeline?
   - What API endpoints does it expose?
   - How does AVAROS skill connect to it?

3. **PREVENTION Setup:**
   - What is the Docker image name/tag?
   - What data format does it expect?
   - What API endpoints for anomaly queries?
   - How does AVAROS skill connect to it?

4. **Integration Pattern:**
   - Do DocuBoT/PREVENTION join the `ovos` network?
   - Do they need RENERYO API credentials?
   - Or does AVAROS skill call them, then they call RENERYO?

---

## 📦 Next Steps

### Immediate (Can Do Now):
- [x] Clone WASABI OVOS repository ✅
- [x] Understand WASABI architecture ✅
- [x] Create AVAROS Docker deployment ✅
- [ ] Deploy WASABI stack locally
- [ ] Deploy AVAROS skill locally
- [ ] Test with mock data

### Waiting for Clarification:
- [ ] Get DocuBoT service details
- [ ] Get PREVENTION service details
- [ ] Get RENERYO API credentials
- [ ] Understand full backend architecture

### After Clarification:
- [ ] Update AVAROS adapters with real endpoints
- [ ] Integrate DocuBoT service
- [ ] Integrate PREVENTION service
- [ ] Production deployment

---

## 📚 Files Created/Updated

1. **DEC-009:** DocuBoT/PREVENTION not in WASABI (decision updated)
2. **DEC-010:** AVAROS as separate Docker service (new decision)
3. **This guide:** Complete deployment instructions

---

## 🆘 Support

### WASABI OVOS Issues:
**Contact:** BIBA team  
**Email:** wel@biba.uni-bremen.de  
**Available:** January 2026 telco support

### AVAROS Development:
**Team:** Lead Developer + Emre  
**Agents:** @planner, @lead-dev, @quality, @git

---

**Status:** WASABI OVOS cloned and understood. Ready to deploy. Need clarification on DocuBoT/PREVENTION.
