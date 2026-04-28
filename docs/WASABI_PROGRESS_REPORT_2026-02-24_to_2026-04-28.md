# AVAROS Technical Progress Report for WASABI Follow-Up

**Period covered:** 2026-02-24 to 2026-04-28  
**Meeting context:** WASABI consortium follow-up since the 2026-02-24 meeting  
**Current milestone framing:** End of M5, moving toward the M6 beta release  
**Technical focus:** DIA development, PREVENTION analytics, voice assistant readiness, platform-agnostic configuration, Docker deployment, and WASABI Shop readiness.

---

## 1. Executive Summary

Since the February 24 follow-up, AVAROS has progressed from the initial assistant foundation into a demonstrable Digital Intelligent Assistant (DIA) stack:

- The OVOS voice assistant can answer manufacturing KPI, trend, comparison, anomaly, drift, status, and asset-related questions.
- The setup flow now supports the platform-agnostic concept expected by WASABI: adapters, metric mappings, asset registration, profiles, and wizard-driven configuration.
- PREVENTION is connected as the analytics backend for anomaly detection and drift monitoring.
- The stack is runnable in Docker with AVAROS, the web UI, OVOS services, wake-word service, HiveMind voice bridge, PREVENTION, and MongoDB.
- The AVAROS DIA stack has a concrete live demo path: system status, anomaly scan, targeted anomaly, carbon anomaly, and drift monitoring.
- A WASABI White Label Shop instance has been cloned and brought up on the ArtiBilim server as an early distribution-channel readiness step.

**Main technical message:**

> At the end of M5, the core AVAROS DIA stack is working, PREVENTION analytics are live, and proposal-relevant use cases can be demonstrated for electricity, material efficiency, CO2, and supplier/production risk signals. Remaining technical work is mainly M6 hardening, documentation consolidation, authenticated PREVENTION deployment, DocuBoT clarification, and final regression testing.

---

## 2. Progress Since the February Meeting

### 2.1 Voice Assistant and KPI Coverage

AVAROS now supports natural-language interaction around the manufacturing metrics needed for the WASABI experiment:

- Energy: energy per unit, total energy, peak demand, peak tariff exposure.
- Material: scrap rate, rework rate, material efficiency, recycled content.
- Production: OEE, throughput, cycle time, changeover time.
- Carbon: CO2 per unit, CO2 total, CO2 per batch.
- Supplier: lead time, defect rate, on-time delivery, supplier CO2 per kg.

The assistant can answer:

- Current KPI questions.
- Trend questions.
- Comparison questions across assets.
- Broad anomaly scans.
- Targeted anomaly checks.
- Drift monitoring questions.
- System/profile/status questions.

### 2.2 Platform-Agnostic Configuration

The work since February strengthened the platform-agnostic approach:

- A configurable adapter reads from a REST-style data source.
- The wizard guides users through connection, assets, metric mapping, and intent activation.
- Metric availability controls which voice intents can be enabled.
- Profiles allow separate configurations for different environments.
- Asset registration and mapping make the assistant aware of factory terms such as Line-1 and Line-2.

**Technical summary:**

> The platform-agnostic concept is now reflected in the actual setup flow. AVAROS does not require a new voice skill for every backend. The integration is handled through adapters, metric mappings, assets, and profiles.

### 2.3 PREVENTION Analytics

PREVENTION is now connected as the analytics backend for anomaly detection and drift monitoring. It is not just a placeholder in the architecture.

Implemented capability:

- PREVENTION GraphQL connectivity.
- Analytics goals for energy, production, material, carbon, and supplier categories.
- Anomaly outputs with metric, asset, timestamp, value, z-score, severity, and spike/dip classification.
- Drift outputs with metric, asset, direction, rate, R-squared, and periods analyzed.
- AVAROS voice responses that translate analytics into operator-facing language.
- Runtime status checks so AVAROS can report whether PREVENTION is healthy, disabled, or unreachable.

**Technical summary:**

> The main technical evidence for M5 is the PREVENTION integration. AVAROS can now show live anomaly and drift results for material efficiency, carbon, energy, production, and supplier-related indicators, and those results are available through the voice assistant.

### 2.4 Voice, Wake Word, and Web Interaction

The assistant is now demonstrable through the running stack:

- Web UI configuration and status checks.
- Browser/voice path through HiveMind and OVOS.
- Wake-word service for the browser voice experience.
- Tested utterances that return spoken responses for KPI, anomaly, drift, and status flows.

### 2.5 Dockerized Running Stack

The current technical demo stack includes:

- AVAROS skill service.
- FastAPI/React web UI.
- OVOS core and message bus.
- HiveMind voice bridge.
- Wake-word service.
- PREVENTION analytics service.
- MongoDB for PREVENTION.
- WASABI White Label Shop instance for early distribution-channel readiness.

### 2.6 WASABI Shop Readiness

A PrestaShop-based WASABI White Label Shop instance has been cloned and deployed on the ArtiBilim Ubuntu server.

Current shop access:

```text
Storefront: http://avaros.int.arti.ac:8083/
Back office: http://avaros.int.arti.ac:8083/wasabiSHOP/
```

Current status:

- The shop containers are running.
- The storefront is reachable.
- The back-office login page is reachable.
- The database contains the expected WASABI admin account and existing shop product records.
- The current intended shop listing content is the developed AVAROS OVOS skill together with Docker deployment assets, installation checklist, sample configuration, screenshots/metadata, and replication notes.
- Final publication content depends on the M6 hardening result and DocuBoT availability/clarification.

### 2.7 DocuBoT Status

The current live demo focuses on PREVENTION, voice interaction, and platform configuration. The DocuBoT integration path is prepared at architecture level, but final live integration depends on receiving the consortium-provided DocuBoT Docker image/access and confirming the indexing contract.

---

## 3. Live Demo Verification on 2026-04-28

The following checks were run successfully on 2026-04-28 in the local AVAROS/PREVENTION stack.

### 3.1 Demo Pre-Check

Before the voice demo, the AVAROS status endpoint confirms that the stack is configured and connected to PREVENTION:

```bash
set -a; source .env; set +a
curl -s http://localhost:8080/api/v1/status \
  -H "X-API-Key: $AVAROS_WEB_API_KEY" \
  | jq -r '"configured=\(.configured) adapter=\(.active_adapter) live=\(.live_connection_state) intents=\(.loaded_intents) prevention=\(.prevention_state) verified=\(.prevention_verified) endpoint=\(.prevention_endpoint)"'
```

Verified output:

```text
configured=true adapter=custom_rest live=healthy intents=34 prevention=healthy verified=true endpoint=http://prevention:8081
```

Service start command used for the verified M5 demo environment:

```bash
set -a; source .env; set +a
PREVENTION_URL=http://prevention:8081 docker compose up -d --force-recreate avaros avaros-web-ui
```

### 3.2 PREVENTION Direct Checks with curl

These checks show PREVENTION returning analytics directly before the same results are demonstrated through the voice layer.

#### Check Available Analytics Goals

```bash
curl -s http://localhost:8082/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ allAnalysis { name analyticsGoal } }"}' \
  | jq -r '.data.allAnalysis | map(.analyticsGoal) | unique | "analytics_goals=\(. | length)\n" + (join("\n"))'
```

Verified output:

```text
analytics_goals=10
CO2_ANOMALY_CHECK
CO2_DRIFT_CHECK
ENERGY_ANOMALY_CHECK
ENERGY_DRIFT_CHECK
MATERIAL_ANOMALY_CHECK
MATERIAL_DRIFT_CHECK
PRODUCTION_ANOMALY_CHECK
PRODUCTION_DRIFT_CHECK
SUPPLIER_ANOMALY_CHECK
SUPPLIER_DRIFT_CHECK
```

#### Material Efficiency Anomaly

```bash
curl -s http://localhost:8082/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ resultRequest(request: [{request: [\"MATERIAL_ANOMALY_CHECK\"]}]) { results reason } }"}' \
  | jq -r '.data.resultRequest[0].results | sort_by(.z_score) | reverse | "material_anomaly_results=\(. | length)\nworst=" + (.[0] | "\(.metric_name) \(.asset_id) \(.anomaly_type) z=\(.z_score) severity=\(.severity) value=\(.value) at \(.timestamp)")'
```

Verified output:

```text
material_anomaly_results=57
worst=material_efficiency Line-2 dip z=3.4467 severity=high value=96.8292 at 2026-04-13 12:00:00
```

#### Carbon Drift

```bash
curl -s http://localhost:8082/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ resultRequest(request: [{request: [\"CO2_DRIFT_CHECK\"]}]) { results reason } }"}' \
  | jq -r '.data.resultRequest[0].results | sort_by(.r_squared) | reverse | "co2_drift_results=\(. | length)\nstrongest=" + (.[0] | "\(.metric_name) \(.asset_id) direction=\(.drift_direction) rate=\(.drift_rate) r2=\(.r_squared) periods=\(.periods_analyzed)")'
```

Verified output:

```text
co2_drift_results=6
strongest=co2_per_unit Line-1 direction=increasing rate=0.009918 r2=0.464 periods=30
```

#### Energy Drift

```bash
curl -s http://localhost:8082/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ resultRequest(request: [{request: [\"ENERGY_DRIFT_CHECK\"]}]) { results reason } }"}' \
  | jq -r '.data.resultRequest[0].results | sort_by(.r_squared) | reverse | "energy_drift_results=\(. | length)\nstrongest=" + (.[0] | "\(.metric_name) \(.asset_id) direction=\(.drift_direction) rate=\(.drift_rate) r2=\(.r_squared) periods=\(.periods_analyzed)")'
```

Verified output:

```text
energy_drift_results=8
strongest=energy_total Line-1 direction=increasing rate=15.87244 r2=0.4759 periods=30
```

---

## 4. Verified Voice Demo Utterances

These utterances were tested through the OVOS messagebus on 2026-04-28 after AVAROS was started with PREVENTION enabled.

| Demo purpose | Demo utterance | Verified response |
|---|---|---|
| System readiness | "Show system status" | "System is online. Active profile is reneryo on platform custom_rest, and adapter is GenericRestAdapter. Prevention mode is http (env_prevention_url)." |
| Broad anomaly scan | "Are there any unusual patterns today?" | "I found anomalies in 30 of 63 checks. Top: supplier on time dipped on Line-2 at 4.1 sigma; material efficiency dipped on Line-2 at 3.5 sigma; supplier defect rate spiked on Line-2 at 2.9 sigma." |
| Targeted energy anomaly | "Check anomalies for energy per unit on Line-1" | "No unusual patterns detected. Energy per unit looks normal." |
| Targeted scrap anomaly | "Check anomalies for scrap rate on Line-2" | "scrap rate spiked, at 2.8 sigma with medium severity on Line-2." |
| Material efficiency anomaly | "Check for anomalies in material efficiency on Line-2" | "material efficiency dipped, at 3.5 sigma with high severity on Line-2." |
| Carbon anomaly | "Check for unusual carbon patterns on Line-2" | "carbon per unit spiked, at 2.5 sigma with medium severity on Line-2." |
| Energy drift | "How has energy per unit been trending?" | "energy per unit is degrading, changing at 0.015 per day over 30 data points." |
| OEE drift | "Is OEE getting worse?" | "No significant drift detected. Overall equipment effectiveness is stable." |
| Carbon drift | "Check for drift in carbon per unit on Line-1" | "carbon per unit is degrading, changing at 0.010 per day over 30 data points." |
| Supplier carbon drift | "Check for drift in supplier co2 per kg on Line-1" | "supplier co2 per kg is degrading, changing at 0.004 per day over 30 data points." |

---

## 5. Live Demo Flow

The M5 follow-up demo sequence is:

1. Show the system status endpoint or say "Show system status".
2. Say "Are there any unusual patterns today?" to show broad PREVENTION anomaly scanning.
3. Say "Check for anomalies in material efficiency on Line-2" to connect to the material-efficiency KPI target.
4. Say "Check for unusual carbon patterns on Line-2" to connect to CO2 monitoring.
5. Say "How has energy per unit been trending?" to connect to electricity-per-unit monitoring.
6. Say "Check for drift in supplier co2 per kg on Line-1" to show supplier-chain risk monitoring.

Demo framing:

> This is not only a dashboard. The operator can ask a natural-language question, AVAROS routes it to the configured manufacturing data source and PREVENTION analytics, then returns a concise explanation with metric, asset, severity, and trend/anomaly context.

---

## 6. Technical Narrative

### Opening

Since the February 24 follow-up, the technical work has focused on making AVAROS demonstrable against the proposal: voice interaction, platform-agnostic configuration, PREVENTION analytics, Dockerized deployment, and WASABI Shop readiness.

### PREVENTION

PREVENTION is now connected as a live analytics backend. AVAROS can show anomaly and drift results for material, carbon, energy, production, and supplier indicators. The voice assistant translates those results into operator-facing responses such as severity, sigma deviation, asset, and trend direction.

### Platform-Agnostic Setup

The platform-agnostic approach is reflected in the adapter and wizard flow. The user configures the data source, assets, metrics, and intent activation. This supports transferability because the assistant logic is not tied to one factory-specific API.

### WASABI Shop

The WASABI White Label Shop instance has been cloned and deployed on the ArtiBilim server. The intended shop content is the developed AVAROS OVOS skill together with Docker deployment assets, sample configuration, installation checklist, screenshots/metadata, and replication material. Final shop content depends on M6 hardening and DocuBoT availability/clarification.

### M6 Technical Closure Items

Before M6 beta closure, the remaining technical closure items are authenticated PREVENTION deployment, documentation consolidation, DocuBoT/grounding scope confirmation, final regression testing, and final shop listing material.

---

## 7. Risks and Open Items

| Item | Risk | Proposed action |
|---|---|---|
| PREVENTION production authentication | Current demo uses the local development PREVENTION path. | Enable and validate authenticated PREVENTION before production-style deployment. |
| DocuBoT grounding | Proposal includes DocuBoT; current live demo focuses on PREVENTION and voice. | Confirm scope once the consortium Docker image/access and indexing contract are available. |
| PREVENTION data freshness | Analytics depend on exported/loaded time-series data. | Define manual or scheduled refresh process for demo and production-style operations. |
| Voice phrasing variability | Natural-language routing depends on intent coverage and tested utterance patterns. | Continue regression testing and expand utterance coverage before wider use. |
| WASABI Shop final listing | The shop instance is running, while the final listing material is still being prepared. | Publish the final AVAROS shop content after beta hardening and DocuBoT scope confirmation. |

---

## 8. Bottom-Line Status

**Strong / ready to show:**

- Platform-agnostic configuration flow.
- Voice assistant for manufacturing KPIs.
- PREVENTION anomaly and drift analytics.
- Dockerized local stack.
- Live demo utterances for material, energy, CO2, supplier, and status.
- WASABI White Label Shop instance deployed on the ArtiBilim server.

**Needs M6 closure:**

- Authenticated PREVENTION deployment.
- Final beta hardening and security checklist.
- Documentation consolidation.
- DocuBoT/grounding decision.
- Final AVAROS shop listing material.

**Closing status:**

> AVAROS is on track technically for the M6 beta release. The strongest M5 evidence is that PREVENTION analytics are no longer theoretical: anomaly and drift checks can be run and demonstrated through both direct API calls and natural-language voice queries. The next step is to harden this validated stack with production-style security, documentation, DocuBoT clarification, and final regression testing.
