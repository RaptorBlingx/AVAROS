# AVAROS Experiment Handbook (EH)

> **Version**: v0.1 (to be updated per Work Package milestones)
> **Deliverable**: D1.3 (M2), D2.3 (M6), D4.2 (M12)

---

## 1. Scope & Objectives

### 1.1 Use Cases
| ID | Use Case | Domain | Priority |
|----|----------|--------|----------|
| UC1 | Query energy per unit | Energy | HIGH |
| UC2 | Compare supplier performance | Supplier | HIGH |
| UC3 | Detect anomalies in production | Anomaly | MEDIUM |
| UC4 | What-if material substitution | What-If | MEDIUM |
| UC5 | Schedule optimization for peak tariff | Schedule | MEDIUM |

### 1.2 KPI Baselines (to be filled during WP1)
| KPI | Baseline Value | Target | Measurement Method |
|-----|----------------|--------|-------------------|
| Electricity per unit | ___ kWh/unit | ≥8% reduction | RENERYO API |
| Material efficiency | ___% | ≥5% improvement | Scrap/rework tracking |
| CO₂-eq | ___ kg CO₂/unit | ≥10% reduction | LCA factors + energy |

---

## 2. Architecture

### 2.1 Component Stack
- OVOS (version: ___)
- DocuBoT (version: ___)
- PREVENTION (version: ___)
- RENERYO Backend (version: ___)

### 2.2 Data Sources
| Source | Type | Format | Refresh Rate |
|--------|------|--------|--------------|
| ERP | Batch data | REST/JSON | Daily |
| MES | Production | REST/JSON | Real-time |
| Sensors | Energy | MQTT | 1 min |
| Suppliers | Declarations | CSV | Monthly |

---

## 3. Governance

### 3.1 Data Classification
- Operational data: INTERNAL
- Supplier declarations: CONFIDENTIAL (anonymize for publication)
- Personal data: MINIMAL (auth logs only)

### 3.2 Access Control
| Role | Access Level |
|------|--------------|
| Operator | Read KPIs |
| Planner | Read + What-If |
| Admin | Full access |

### 3.3 Audit Trail
- All queries logged with timestamp, user_role, intent
- Recommendations include unique IDs for traceability

---

## 4. Development Progress

### 4.1 Alpha Release (M3)
- [ ] Core intents implemented
- [ ] RENERYO adapter working
- [ ] Basic DocuBoT integration

### 4.2 Beta Release (M6)
- [ ] All 5 query types functional
- [ ] PREVENTION anomaly detection integrated
- [ ] Security checklist passed

---

## 5. Pilot Validation

### 5.1 Pilot Sites
| Site | Type | Start | End |
|------|------|-------|-----|
| ArtiBilim Plastics | Development testbed | M1 | M6 |
| AI EDIH Factory | Production pilot | M5 | M10 |
| MEXT Digital Factory | Transferability demo | M5 | M10 |

### 5.2 KPI Results (to be filled M10)
| KPI | Baseline | Endline | Δ% | Target Met? |
|-----|----------|---------|-----|-------------|
| Electricity/unit | | | | |
| Material efficiency | | | | |
| CO₂-eq | | | | |

---

## 6. Replication & Exploitation

### 6.1 WASABI Shop Listing
- [ ] Dockerized release
- [ ] Installation checklist
- [ ] Sample configuration
- [ ] Getting-started dataset

### 6.2 Post-Project Sustainability
- RENERYO integration maintained by ArtiBilim
- Open-source skill available via Shop
- AI EDIH TÜRKIYE onboarding support

---

## Changelog
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v0.1 | M2 | | Initial structure |
| v0.2 | M6 | | Alpha/Beta notes |
| v1.0 | M12 | | Final with KPI results |
