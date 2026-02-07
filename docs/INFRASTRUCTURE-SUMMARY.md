# AVAROS - Infrastructure Summary

**Last Updated:** February 5, 2026

---

## 🎯 What You Have

### From WASABI Email:
✅ **Private Docker Compose for OVOS**
- Repository: https://gitlab.ips.biba.uni-bremen.de/...
- Deployment token (expires: January 31, 2027)
- README with deployment instructions
- License file with restrictions
- Support from BIBA team available

### What This Means:
1. **OVOS infrastructure is PROVIDED** - You don't build it from scratch
2. **AVAROS skill installs INTO OVOS** - This repo is a skill that plugs into their OVOS
3. **Docker-based deployment** - Everything runs in containers
4. **Battle-tested** - WASABI maintains the OVOS stack

---

## ✅ Architecture Clarified (From WASABI Proposal)

### The Full AVAROS Stack:

**From Proposal Section 1.2:**
> "AVAROS adds three WASABI-stack components: OVOS for the conversational layer, DocuBoT to retrieve and ground answers in procedures, specifications and pilot documentation, and PREVENTION to support early detection of anomalies and risks in operations and supply flows."

```
User Voice/Text
       ↓
 [WASABI OVOS] ← Provided (cloned from GitLab)
       ↓
 [AVAROS Skill] ← We build (this repo)
    ↙     ↘
[DocuBoT] [PREVENTION] ← WASABI components (need to request)
    ↘     ↙
   [RENERYO] ← ArtiBilim's data platform
       ↓
[ERP/MES/IoT] ← Factory systems
```

### Component Breakdown:

1. **WASABI OVOS** (✅ Cloned)
   - Source: WASABI GitLab repository
   - Status: Available at `/home/ubuntu/wasabi-ovos`
   - Provides: Voice interface, message bus, Keycloak, Nginx

2. **AVAROS Skill** (🔨 In Development)
   - Source: This repository
   - Status: Active development
   - Provides: Intent handlers, query dispatch, response building

3. **DocuBoT** (⏳ Need to Request)
   - Source: WASABI consortium component
   - Status: **Not in WASABI OVOS repo** (confirmed by search)
   - Purpose: RAG for ISO 50001 procedures/specs
   - **Action:** Request from WASABI (Section 1.4: "We will request setup and configuration guidance")

4. **PREVENTION** (⏳ Need to Request)
   - Source: WASABI consortium component
   - Status: **Not in WASABI OVOS repo** (confirmed by search)
   - Purpose: Anomaly detection in operations/supply flows
   - **Action:** Request from WASABI (Section 1.4: "We will request integration guidance")

5. **RENERYO** (🏭 External)
   - Source: ArtiBilim's existing platform
   - Status: Separate proprietary backend
   - Provides: Manufacturing data, supplier data, KPIs

---

## ❓ Questions for WASABI Consortium

Based on Proposal Section 1.4 ("Collaboration with the WASABI team"):

### DocuBoT Access:
- How do we access DocuBoT? (Separate GitLab repo? Docker Hub? Same token?)
- What is the Docker image name/tag?
- Configuration guidance for indexing pipeline?
- API documentation and endpoints?

### PREVENTION Access:
- How do we access PREVENTION? (Separate repo? Docker image?)
- What is the Docker image name/tag?
- Data schemas and API endpoints?
- Integration guidance for energy/material/CO₂ KPIs?

### Integration Pattern:
- Do DocuBoT/PREVENTION join the `ovos` network?
- Does AVAROS call them directly, or do they call RENERYO?
- Authentication/authorization between services?

---

## 📐 Old Architecture (For Reference)

```
┌──────────────────────────────────────────────────┐
│  WASABI OVOS Stack (Docker Compose)              │
│  https://gitlab.ips.biba.uni-bremen.de           │
│  ┌────────────────────────────────────────────┐  │
│  │  OVOS Core                                 │  │
│  │  - Wake word detection                     │  │
│  │  - Speech-to-Text (STT)                    │  │
│  │  - Text-to-Speech (TTS)                    │  │
│  │  - Message Bus                             │  │
│  │  - Audio Backend                           │  │
│  └────────────────────────────────────────────┘  │
│                    ↓                              │
│  ┌────────────────────────────────────────────┐  │
│  │  AVAROS Skill (avaros-ovos-skill/)        │  │ ← THIS REPO
│  │                                            │  │
│  │  Intent Handlers → Query Dispatcher       │  │
│  │       ↓                                    │  │
│  │  Manufacturing Adapter Interface           │  │
│  │       ↓                                    │  │
│  │  [MockAdapter | RENERYOAdapter | ...]     │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                    ↓ HTTP/REST API
┌──────────────────────────────────────────────────┐
│  Backend Services (Clarification Needed)         │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  DocuBoT (RAG)                             │ │ ← ❓ Where/how deployed?
│  │  - ISO 50001 procedures                    │ │
│  │  - Technical specifications                │ │
│  │  - Q&A on documentation                    │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  PREVENTION (Anomaly Detection)            │ │ ← ❓ Where/how deployed?
│  │  - Time-series analysis                    │ │
│  │  - Pattern detection                       │ │
│  │  - Alert generation                        │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  RENERYO or SAP (Data Platform)            │ │ ← Manufacturer provides
│  │  - Energy KPIs                             │ │
│  │  - Material data                           │ │
│  │  - Production metrics                      │ │
│  │  - Supplier information                    │ │
│  └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

---

## 🚀 Deployment Strategy

### Phase 1: Demo Mode (Zero-Config)
```bash
# 1. Deploy WASABI OVOS
cd wasabi-ovos && docker-compose up -d

# 2. Install AVAROS skill
cd avaros-ovos-skill && python -m skill

# 3. Test with mock data
# Say: "Hey Mycroft, what's our energy per unit?"
# AVAROS responds with mock data
```

**Works with:**
- ✅ MockAdapter (built-in, no backend needed)
- ✅ Mock DocuBoT responses
- ✅ Mock PREVENTION alerts

### Phase 2: Real Backend Integration
```bash
# 1. Configure RENERYO adapter
# Via Web UI: http://localhost:8000/settings
# Or environment variables:
export ADAPTER_TYPE=reneryo
export RENERYO_API_URL=https://...
export RENERYO_API_KEY=...

# 2. Connect DocuBoT (once clarified)
export DOCUBOT_API_URL=https://...

# 3. Connect PREVENTION (once clarified)
export PREVENTION_API_URL=https://...

# 4. Restart skill
docker-compose restart
```

---

## 📋 Next Actions

### Immediate (Can Start Now)
1. ✅ Clone WASABI OVOS repository
2. ✅ Deploy OVOS stack following their README
3. ✅ Install AVAROS skill in demo mode
4. ✅ Test voice interaction with mock data
5. ✅ Review architecture documentation

### Need Clarification (Ask WASABI/BIBA)
1. ❓ **DocuBoT deployment:** Separate service? Part of RENERYO? API endpoints?
2. ❓ **PREVENTION deployment:** Separate service? Real-time or batch? API format?
3. ❓ **OVOS skill installation path:** Where exactly does AVAROS install in WASABI OVOS?
4. ❓ **Service discovery:** How does AVAROS find DocuBoT/PREVENTION services?

### Future (After Clarification)
1. Configure real RENERYO/SAP backend
2. Integrate actual DocuBoT service
3. Integrate actual PREVENTION service
4. Production deployment

---

## 📚 Key Documents

| Document | What It Covers |
|----------|----------------|
| [DEPLOYMENT-SETUP.md](docs/DEPLOYMENT-SETUP.md) | Detailed deployment instructions with all steps |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and design principles |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture decisions (DEC-008, DEC-009, DEC-010 added) |
| [TODO.md](docs/TODO.md) | Development task tracker |
| [AGENT-SYSTEM-PLAN.md](docs/AGENT-SYSTEM-PLAN.md) | AI agent workflow for development |

---

## 💡 Key Insights

### You Don't Need to Build Everything
- **OVOS**: ✅ Provided by WASABI (Docker Compose - cloned)
- **AVAROS Skill**: 🔨 You build this (this repository)
- **DocuBoT/PREVENTION**: ⏳ WASABI components (need to request from consortium)
- **RENERYO/SAP**: ✅ Provided by manufacturer

### Zero-Config Works Today
- MockAdapter provides sample data
- No backend configuration needed for demos
- Full voice interaction works out-of-box
- Perfect for development and testing

### Production Requires Adapter Configuration
- Swap MockAdapter for RENERYOAdapter
- Provide API credentials via Web UI or env vars
- Connect to real manufacturing data
- No code changes needed (just configuration)

---

## 🆘 Support

### OVOS Deployment Questions
**Contact:** BIBA team  
**Via:** Email from WASABI  
**Available:** January 2026 for support telco

### DocuBoT/PREVENTION Questions
**Ask:** WASABI/BIBA team  
**Questions:** Deployment method, API contracts, service locations

### AVAROS Development Questions
**Use:** AI agents in this repository
- `@planner` - Task planning
- `@lead-dev` - Lead developer coding
- `@quality` - Code review
- `@git` - Git operations

---

**Summary:** You have OVOS infrastructure (from WASABI). Build AVAROS skill (this repo). Clarify DocuBoT/PREVENTION deployment.
