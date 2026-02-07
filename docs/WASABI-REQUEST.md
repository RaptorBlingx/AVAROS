# Request for DocuBoT and PREVENTION Access

**Date:** February 5, 2026  
**Project:** AVAROS (WASABI Open Call Experiment)  
**From:** ArtiBilim + AI EDIH TÜRKIYE

---

## Summary

We successfully cloned the WASABI OVOS repository using the deployment token provided. After thorough exploration, we confirmed that **DocuBoT and PREVENTION are not included** in the WASABI OVOS GitLab repository.

Based on our proposal (Sections 1.2, 1.3, 1.4), we understand these are **WASABI-stack components** that need to be requested separately from the consortium.

---

## What We've Done

### ✅ WASABI OVOS Access
- Successfully cloned: https://gitlab.ips.biba.uni-bremen.de/.../docker-compose-project-for-ovos
- Using deployment token: `gldt-dnQ-yHVwJcHLxk7LxTUq`
- Repository explored: 53 files/directories
- Services identified: OVOS Core, Message Bus, Hivemind, Keycloak, Nginx, Dozzle

### ✅ Verification Searches Completed
We performed exhaustive searches to confirm DocuBoT/PREVENTION are not in WASABI OVOS:
- Searched all files for: "docu", "docubot", "DocuBoT" → Only found "documentation"
- Searched all files for: "prevent", "PREVENTION" → Only found "prevent" (permissions context)
- Searched for all AVAROS terms: "avaros|reneryo|prevention|docubot|rag|anomaly" → **Zero results**
- Examined all 8 docker-compose files → Only OVOS infrastructure services listed
- Read README.md (comprehensive) → No backend service mentions
- Read license file → BIBA copyright, WASABI scope only

**Conclusion:** WASABI OVOS provides only the voice assistant infrastructure. DocuBoT and PREVENTION are separate components.

---

## Architecture Understanding (From Our Proposal)

### From Section 1.2:
> "AVAROS adds three WASABI-stack components: **OVOS** for the conversational layer, **DocuBoT** to retrieve and ground answers in procedures, specifications and pilot documentation, and **PREVENTION** to support early detection of anomalies and risks in operations and supply flows."

### From Section 1.3:
> "The assistant will be implemented with **OVOS** (skill, intent handling, dialogue), **DocuBoT** (retrieval grounding over procedures, specifications and pilot documentation), and **PREVENTION** (early warnings on anomalous patterns in operations and supply flows). These components will run in a Docker-Compose stack and will be wired to RENERYO via documented REST APIs."

### Architecture Flow:
```
User Voice/Text
       ↓
 [WASABI OVOS] ← ✅ Cloned and ready
       ↓
 [AVAROS Skill] ← 🔨 In development (this repository)
    ↙     ↘
[DocuBoT] [PREVENTION] ← ⏳ NEED ACCESS (not in WASABI OVOS repo)
    ↘     ↙
   [RENERYO] ← ArtiBilim's existing data platform
       ↓
[ERP/MES/IoT] ← Factory systems
```

---

## What We Need

### 1. DocuBoT Access

**Purpose:** Retrieval-Augmented Generation for document grounding (ISO 50001 procedures, specifications, pilot documentation)

**Questions:**
- How do we access DocuBoT?
  - Separate GitLab repository?
  - Docker Hub image?
  - Same deployment token or different credentials?
- What is the Docker image name and tag?
- Configuration guidance:
  - How to set up the indexing pipeline?
  - How to configure multilingual support?
  - Recommended resource sizing?
- API documentation:
  - What endpoints does DocuBoT expose?
  - How does AVAROS skill connect to it?
  - Authentication/authorization requirements?
- Integration pattern:
  - Does DocuBoT join the `ovos` Docker network?
  - Does AVAROS call DocuBoT directly?
  - Or does DocuBoT need to call RENERYO for context?

**From Proposal Section 1.4:**
> "DocuBoT (retrieval grounding): We will request setup and configuration guidance to confirm the indexing pipeline and grounding patterns (procedures, specifications, pilot documentation), including multilingual support and recommended resource sizing within our stack."

---

### 2. PREVENTION Access

**Purpose:** Anomaly/drift detection for energy, material, and CO₂-eq KPIs in operations and supply flows

**Questions:**
- How do we access PREVENTION?
  - Separate GitLab repository?
  - Docker Hub image?
  - Same deployment token or different credentials?
- What is the Docker image name and tag?
- Integration guidance:
  - What data schemas does PREVENTION expect?
  - What API endpoints are available?
  - Recommended parameters for drift checks?
  - Alerting threshold configuration for pilot conditions?
- Data flow:
  - Real-time processing or batch?
  - Does AVAROS query PREVENTION for anomalies?
  - Or does PREVENTION push alerts to AVAROS?
- Integration pattern:
  - Does PREVENTION join the `ovos` Docker network?
  - Does it need direct access to RENERYO?
  - Authentication/authorization requirements?

**From Proposal Section 1.4:**
> "PREVENTION (anomaly/drift): We will request integration guidance focused on data schemas and API endpoints relevant to energy/material/CO₂-eq KPIs, plus recommended parameters for drift checks and alerting thresholds in pilot conditions."

---

### 3. Deployment Integration

**Questions:**
- Do DocuBoT and PREVENTION deploy in the same Docker Compose stack as WASABI OVOS?
- Or separate stacks that communicate over network?
- Do they share the `ovos` network?
- Do they need to mount any shared volumes from WASABI OVOS (like `ovos/config` or `ovos/tmp`)?
- What environment variables or configuration files are required?

---

## Current Status & Next Steps

### ✅ Completed:
1. WASABI OVOS repository cloned and explored
2. AVAROS skill architecture designed
3. Domain models, adapters, and use cases implemented
4. MockAdapter working for development
5. Documentation updated with architecture clarifications

### ⏳ Blocked Waiting for DocuBoT/PREVENTION:
1. Cannot implement DocuBoT integration layer
2. Cannot implement PREVENTION anomaly detection hooks
3. Cannot test full stack integration
4. Cannot deploy complete AVAROS Docker Compose stack

### 🔄 Interim Approach:
- Continuing development with mock implementations:
  - `skill/services/docubot_mock.py` (placeholder)
  - `skill/services/prevention_mock.py` (placeholder)
- These will be replaced with real integrations once we have access

---

## Timeline Impact

**From Proposal Work Plan:**
- **WP2 (M1-M6):** DIA Development - Needs DocuBoT/PREVENTION by M3 for Alpha
- **WP3 (M5-M10):** Dual Pilots - Needs full stack integration by M5

**Request Urgency:** We need access to DocuBoT and PREVENTION **by end of February 2026** to stay on schedule for Alpha release (M3 = March 2026).

---

## Contact Information

**Lead Developer:** [Your Name]  
**Company:** ArtiBilim Bilgi ve Egitim Teknolojileri San. Tic. Ltd. Sti.  
**Partner:** AI EDIH TÜRKIYE  
**Deployment Token:** gldt-dnQ-yHVwJcHLxk7LxTUq (expires 2027-01-31)

---

## Proposed Next Steps

1. **WASABI Consortium Response:**
   - Provide access instructions for DocuBoT
   - Provide access instructions for PREVENTION
   - Share Docker images, API documentation, configuration examples

2. **ArtiBilim Actions:**
   - Integrate DocuBoT into AVAROS skill
   - Integrate PREVENTION into AVAROS skill
   - Update docker-compose stack
   - Test end-to-end integration

3. **Joint Session (Optional):**
   - Setup call with WASABI team to review integration approach
   - Clarify any deployment questions
   - Review security/authentication patterns

---

**Thank you for your support!**

We look forward to integrating these WASABI components into AVAROS and delivering a successful experiment for the WASABI Open Call.
