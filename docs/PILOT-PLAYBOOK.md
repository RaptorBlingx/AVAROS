# AVAROS Pilot Deployment Playbook

## D3.1 — Pilot Implementation Plan

**Version:** 1.0
**Date:** February 2026
**Experiment:** WASABI OC2 — AVAROS
**Deliverable:** D3.1 Pilot Implementation Plan (due M5, June 2026)

---

## 1. Overview

AVAROS is an AI voice assistant for manufacturing environments. It provides conversational access to energy, material, production, and carbon KPIs using natural language queries. Operators can ask questions like "What's our energy per unit?" and receive spoken answers drawn from real-time production data.

### What This Pilot Measures

The WASABI experiment validates AVAROS against three KPI targets:

| # | KPI | Target | Measurement |
|---|-----|--------|-------------|
| 1 | Electricity per unit | ≥ 8% reduction | kWh consumed per unit produced |
| 2 | Material efficiency | ≥ 5% improvement | Scrap rate reduction |
| 3 | CO₂ emissions | ≥ 10% reduction | kg CO₂-eq per unit produced |

### Timeline

| Milestone | Month | Period | Action |
|-----------|-------|--------|--------|
| Deployment | M5–M6 | Jun–Jul 2026 | Install AVAROS at pilot sites |
| Baseline | M7 | Aug 2026 | Record initial KPI values |
| Midline | M8–M9 | Sep–Oct 2026 | Continue operations, check progress |
| Endline | M10 | Nov 2026 | Final measurement, compare to baseline |
| Report | M10 | Nov 2026 | Generate D3.2 Validation Report data |
| Publication | M11–M12 | Dec 2026–Jan 2027 | WASABI White-Label Shop package |

### Roles

| Role | Responsibility |
|------|---------------|
| **Project Lead** | Oversees deployment, coordinates with WASABI consortium |
| **Site Operator** | Runs daily KPI checks, uploads production data, uses voice commands |
| **Developer** | Maintains system, resolves technical issues, updates software |

---

## 2. Prerequisites

### Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB free | 40 GB free |
| OS | Linux (Ubuntu 22.04+) | Ubuntu 24.04 LTS |
| Docker | Docker Engine 24+ | Latest stable |
| Docker Compose | v2.20+ | Latest stable |

### Network Requirements

| Requirement | Detail |
|-------------|--------|
| HTTPS access | Port 443 open for Web UI and API access |
| HTTP access | Port 80 open (redirects to HTTPS) |
| RENERYO API | Outbound HTTPS to RENERYO platform URL |
| OVOS message bus | Internal Docker network (port 8181, not exposed externally) |
| DNS | A record pointing to the server (for Let's Encrypt certificates) |

### Accounts and Credentials

| Item | Source | How to Obtain |
|------|--------|---------------|
| RENERYO API access | ArtiBilim / RENERYO platform | Request from ArtiBilim operations team |
| Server SSH access | Project infrastructure | Contact Project Lead |
| WASABI OVOS images | BIBA (WASABI consortium) | Deploy token provided during onboarding |

---

## 3. Installation Procedure

### Step 1: Clone the Repository

```bash
git clone https://code.arti.ac/europe/AVAROS.git avaros-ovos-skill
cd avaros-ovos-skill
```

### Step 2: Create the Environment File

```bash
cp .env.example .env
```

Open `.env` in a text editor and configure the values. See the [Environment Variable Reference](ENV-REFERENCE.md) for a complete list.

At minimum, set:

| Variable | What to Enter |
|----------|---------------|
| `ADAPTER_TYPE` | `reneryo` (for production) or `mock` (for demo) |
| `AVAROS_DATABASE_URL` | PostgreSQL connection URL (default works for Docker) |
| `AVAROS_WEB_API_KEY` | A secure API key (generate with the command below) |

Generate a secure API key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the `AVAROS_WEB_API_KEY` value in `.env`.

### Step 3: Create the Docker Network

The AVAROS services communicate on a shared Docker network called `ovos`:

```bash
docker network create ovos
```

> **Note:** If the WASABI OVOS stack is already running, the `ovos` network may already exist. If the command returns an error saying the network already exists, that is fine — continue to the next step.

### Step 4: Generate TLS Certificates

#### Option A: Self-Signed Certificate (for Testing)

```bash
cd docker/nginx
./generate-dev-cert.sh
cd ../..
```

> Self-signed certificates will show a browser warning. This is acceptable for internal testing.

#### Option B: Let's Encrypt (for Production)

1. Ensure your server has a public DNS name (e.g., `avaros.artibilim.com`)
2. Ensure ports 80 and 443 are open to the internet
3. Set `AVAROS_TLS_MODE=letsencrypt` in your `.env` file
4. Start the services (Step 5) — the certificate will be obtained automatically
5. Set up automatic renewal:

```bash
# Add to crontab (runs twice daily)
echo "0 */12 * * * /path/to/avaros-ovos-skill/docker/certbot-renew.sh" | crontab -
```

### Step 5: Start the Docker Stack

```bash
docker compose -f docker/docker-compose.avaros.yml up -d
```

This starts five services:

| Service | Purpose |
|---------|---------|
| `avaros_db` | PostgreSQL database for settings, baselines, and production data |
| `avaros_skill` | OVOS voice skill (connects to OVOS message bus) |
| `avaros-web-ui` | Web interface for configuration and KPI dashboard |
| `reneryo-mock` | Mock RENERYO server for testing (can be disabled in production) |
| `avaros-proxy` | Nginx reverse proxy with HTTPS/TLS termination |

### Step 6: Verify All Services Are Running

```bash
docker compose -f docker/docker-compose.avaros.yml ps
```

All services should show `healthy` status. If a service shows `unhealthy`, check its logs:

```bash
docker compose -f docker/docker-compose.avaros.yml logs <service-name>
```

### Step 7: Verify HTTPS Access

```bash
curl -k https://localhost/health
```

Expected response:

```json
{"status": "healthy"}
```

### Step 8: Open the Web UI

Open your browser and navigate to:

```
https://<your-server-address>
```

You should see the AVAROS Web UI. If this is the first time, the First-Run Wizard will appear automatically.

---

## 4. First-Run Configuration (Web UI Wizard)

The Web UI wizard guides you through initial setup in 6 steps.

### Step 1: Welcome

The welcome screen introduces AVAROS and explains what the wizard will configure. Click **Next** to continue.

### Step 2: Platform Selection

Select your manufacturing data platform:

| Option | When to Use |
|--------|-------------|
| **Demo Mode** | Testing without external connections |
| **RENERYO** | Production deployment with RENERYO energy monitoring |

Select **RENERYO** for pilot deployment. Click **Next**.

### Step 3: RENERYO Credentials

Enter your RENERYO API connection details:

| Field | What to Enter |
|-------|---------------|
| API URL | The base URL of your RENERYO instance (e.g., `https://reneryo.artibilim.com`) |
| Authentication | Cookie-based authentication credentials |
| Timeout | Connection timeout in seconds (recommended: 30) |

> **Note:** Credentials are encrypted before storage using Fernet encryption. They are never stored in plain text.

### Step 4: Test Connection

Click **Test Connection**. The system will:
1. Attempt to connect to the RENERYO API
2. Verify authentication
3. Discover available meters and metrics

**Expected result:** Green status indicator with a list of discovered meters.

**If the test fails:**
- Verify the API URL is correct and reachable from the server
- Check that your credentials are valid
- Ensure the server can reach the RENERYO API (check firewall rules)

### Step 5: Metric Mapping

Map RENERYO metrics to AVAROS canonical metric names:

| AVAROS Metric | Description | Map To |
|---------------|-------------|--------|
| `energy_per_unit` | Energy consumed per unit produced | Select the appropriate RENERYO meter |
| `energy_total` | Total energy consumption | Select the appropriate RENERYO meter |
| `oee` | Overall Equipment Effectiveness | Select source or leave unmapped |
| `scrap_rate` | Material scrap percentage | Select source or leave unmapped |

Only mapped metrics will be available for voice queries and KPI tracking.

### Step 6: Intent Activation

Enable or disable individual voice commands:

| Intent | Default | Description |
|--------|---------|-------------|
| Energy per unit | Enabled | Query energy consumption per unit |
| OEE | Enabled | Query overall equipment effectiveness |
| Scrap rate | Enabled | Query material scrap rate |
| Compare energy | Enabled | Compare energy between two assets |
| Energy trend | Enabled | Show energy consumption trends |
| Scrap trend | Enabled | Show scrap rate trends |
| Anomaly check | Enabled | Check for production anomalies |
| What-if simulation | Enabled | Simulate parameter changes |

Disable intents that are not relevant to your site. Click **Save** to finish the wizard.

---

## 5. Data Source Mapping

### Energy Data (from RENERYO)

RENERYO provides energy consumption data through its API. The key data points:

| Data Point | RENERYO Source | Notes |
|------------|---------------|-------|
| Meter consumption | `GET /api/u/measurement/meter/item` | Aggregated by date range |
| Metric definitions | `GET /api/u/measurement/metric/item` | Metric names and types |

When mapping meters, identify:
- Which RENERYO meters correspond to which production assets (e.g., `Line-1`, `Compressor-1`)
- Which energy resource type each meter tracks (e.g., `ELECTRIC`, `GAS`)
- The measurement units (e.g., kWh)

### Production Data (Manual or ERP Export)

Production data (units produced, shifts, batches) is not available from RENERYO. It must be provided separately:

| Source | Method |
|--------|--------|
| ERP system | Export as CSV and upload via Web UI |
| Shift reports | Enter manually via Web UI |
| Spreadsheets | Convert to CSV format and upload |

See [Section 6: Production Data Setup](#6-production-data-setup) for details.

### Material Data

Material efficiency data (scrap rate, rework rate) can be provided via:
- CSV upload with production data
- Manual entry in the Web UI

### Emission Factors

CO₂ emission factors convert energy consumption to CO₂ equivalents. See [Section 7: Emission Factor Configuration](#7-emission-factor-configuration).

---

## 6. Production Data Setup

### CSV Format

Production data CSV files must follow this format:

| Column | Required | Format | Description |
|--------|----------|--------|-------------|
| `date` | Yes | `YYYY-MM-DD` | Production date |
| `asset` | Yes | Text | Asset or line name (e.g., `Line-1`) |
| `units_produced` | Yes | Number | Units produced in the period |
| `shift` | No | Text | Shift identifier (e.g., `morning`, `afternoon`) |
| `scrap_units` | No | Number | Units scrapped |
| `rework_units` | No | Number | Units reworked |
| `batch_id` | No | Text | Batch identifier |

Example CSV:

```csv
date,asset,units_produced,shift,scrap_units,rework_units
2026-08-01,Line-1,500,morning,12,5
2026-08-01,Line-1,480,afternoon,8,3
2026-08-02,Line-1,510,morning,10,4
```

### How to Upload via Web UI

1. Navigate to **Production Data** in the left menu
2. Click **Upload CSV**
3. Select your CSV file
4. Review the preview — verify column mapping is correct
5. Click **Import**
6. Check the summary for any validation errors

### Manual Entry

1. Navigate to **Production Data** in the left menu
2. Click **Add Record**
3. Fill in the date, asset, and units produced
4. Optionally add scrap and rework counts
5. Click **Save**

### Data Validation

The system validates uploaded data:
- Dates must be in `YYYY-MM-DD` format
- Asset names must match configured assets
- Numeric fields must contain valid numbers
- Duplicate records (same date + asset + shift) are flagged

### Recommended Upload Frequency

Upload production data **daily** or **per shift** to maintain accurate KPI calculations. Delays in uploading reduce the accuracy of energy-per-unit and CO₂-per-unit calculations.

---

## 7. Emission Factor Configuration

CO₂ emissions are calculated by multiplying energy consumption by an emission factor.

### Navigate to Emission Factors

1. Open the Web UI
2. Go to **Settings** → **Emission Factors**

### Select Country Preset

Turkey's electricity grid emission factor:

| Parameter | Value | Source |
|-----------|-------|--------|
| Country | Turkey | — |
| Energy source | Electricity | Grid power |
| Emission factor | 0.48 kg CO₂/kWh | IEA / TUIK (verify current year) |

### Enter the Factor

1. Select energy source: **Electricity**
2. Enter the emission factor: `0.48`
3. Enter the unit: `kg CO₂/kWh`
4. Enter the source reference (e.g., "IEA 2024 Turkey grid factor")
5. Click **Save**

### How Factors Affect Calculations

| Metric | Formula |
|--------|---------|
| CO₂ total | Energy total (kWh) × Emission factor (kg CO₂/kWh) |
| CO₂ per unit | Energy per unit (kWh/unit) × Emission factor (kg CO₂/kWh) |

> **Note:** If the emission factor is not configured, CO₂-related queries will return zero values. Always configure the emission factor before recording the KPI baseline.

---

## 8. KPI Baseline Recording

The baseline is the "before" measurement for the WASABI experiment. It establishes reference values that later measurements are compared against.

> **Important:** Record the baseline only after both energy data (from RENERYO) and production data (from CSV/manual entry) are available for at least 2 weeks.

### Prerequisites

Before recording a baseline, verify:

- [ ] RENERYO connection is active (green status on Dashboard)
- [ ] At least 2 weeks of energy data available in RENERYO
- [ ] At least 2 weeks of production data uploaded to AVAROS
- [ ] Emission factor is configured (see Section 7)
- [ ] Metric mapping is complete (see Section 5)

### Recording Procedure

1. Navigate to the **KPI Dashboard** in the Web UI
2. Click **Record Baseline**
3. Enter the site identifier (e.g., `artibilim-ankara`)
4. Select the measurement period (recommended: last 2 weeks)
5. The system calculates baseline values for all three KPIs:

| KPI | Example Baseline | Unit |
|-----|------------------|------|
| Energy per unit | 2.45 | kWh/unit |
| Scrap rate | 4.2 | % |
| CO₂ per unit | 1.18 | kg CO₂/unit |

6. Review the calculated values carefully
7. Click **Confirm and Lock Baseline**
8. Take a screenshot or export the baseline data for D3.2 evidence

### After Recording

Once the baseline is locked:
- It cannot be modified (prevents accidental changes)
- Progress is calculated automatically as new data arrives
- The KPI Dashboard shows current values vs. baseline
- WASABI targets (8% / 5% / 10%) are displayed as goals

---

## 9. Ongoing Operations

### Voice Commands

Use these voice commands during daily operations. Say "Hey Mycroft" to activate the assistant, then speak your query.

| Say This | You Get |
|----------|---------|
| "What's the energy per unit for Line-1?" | Energy consumption per unit produced |
| "What's the OEE for Line-1?" | Overall Equipment Effectiveness |
| "What's the scrap rate?" | Material scrap percentage |
| "Compare energy between Line-1 and Line-2" | Side-by-side energy comparison |
| "Show the energy trend for last week" | Rising, falling, or stable energy trend |
| "What's the scrap trend for this month?" | Scrap rate trend direction |
| "Are there any anomalies in production?" | Anomaly detection results |
| "What if we reduce temperature by 5 degrees?" | What-if simulation result |

> For a printable reference card, see [Voice Commands Quick Reference](VOICE-COMMANDS.md).

### Reading the KPI Dashboard

The KPI Dashboard shows:

| Element | What It Means |
|---------|---------------|
| Current value | Latest KPI calculation (updates with new data) |
| Baseline value | Locked reference value from baseline recording |
| Progress | Percentage improvement since baseline |
| Target | WASABI target for this KPI (8%, 5%, or 10%) |
| Status | On track (green), at risk (yellow), behind (red) |

### Daily Routine

1. Upload production data for the previous day/shift
2. Check the KPI Dashboard for any alerts
3. Use voice commands to spot-check specific metrics
4. Investigate any anomalies flagged by the system

### Weekly KPI Check

1. Open the KPI Dashboard
2. Review progress for all three KPIs
3. Note any significant changes
4. If energy per unit is rising, investigate production changes
5. If scrap rate is increasing, review material quality

### Monthly Progress Report

1. Navigate to **KPI Progress** → **Export**
2. Select the reporting period
3. Download the anonymized dataset
4. Include in the monthly WASABI progress update to the consortium

---

## 10. Measurement Schedule

| Milestone | Month | Period | Action | KPI Check |
|-----------|-------|--------|--------|-----------|
| Deployment | M5–M6 | Jun–Jul 2026 | Install AVAROS, configure connections | Verify data flow |
| Baseline | M7 | Aug 2026 | Record initial KPI values | Set reference values |
| Midline 1 | M8 | Sep 2026 | Continue operations | Check progress vs. baseline |
| Midline 2 | M9 | Oct 2026 | Continue operations | Assess trend direction |
| Endline | M10 | Nov 2026 | Final measurement | Compare to baseline |
| Report | M10 | Nov 2026 | Generate D3.2 data | Export anonymized dataset |
| Publication | M11–M12 | Dec–Jan 2027 | WASABI White-Label Shop | Package for reuse |

### Data Collection Requirements

| Period | Energy Data | Production Data | Notes |
|--------|-------------|-----------------|-------|
| Baseline (M7) | ≥ 2 weeks continuous | ≥ 2 weeks daily | Must overlap same dates |
| Midline (M8–M9) | Continuous | Daily or per-shift | Monitor trends |
| Endline (M10) | ≥ 2 weeks continuous | ≥ 2 weeks daily | Final measurement period |

---

## 11. Troubleshooting

### Connection Issues

| Problem | Possible Cause | Resolution |
|---------|---------------|------------|
| Connection test fails | Incorrect RENERYO URL | Verify the API URL is correct and includes the protocol (`https://`) |
| Connection test fails | Invalid credentials | Re-enter credentials in the Web UI wizard |
| Connection test fails | Network/firewall | Check that the server can reach the RENERYO API: `curl -I <reneryo-url>` |
| Connection test times out | Slow network | Increase the timeout in platform settings (default: 30s) |

### Data Issues

| Problem | Possible Cause | Resolution |
|---------|---------------|------------|
| No energy data | Meters not mapped | Complete metric mapping in the Web UI (Settings → Metric Mapping) |
| CO₂ shows 0 | Emission factor not set | Configure emission factor in Settings → Emission Factors |
| KPI not computing | No production data | Upload production data CSV or enter records manually |
| CSV upload fails | Wrong format | Check CSV column names match the required format (Section 6) |
| Duplicate records | Same date+asset+shift | Delete duplicates via the Production Data page |

### Voice Issues

| Problem | Possible Cause | Resolution |
|---------|---------------|------------|
| Voice not responding | OVOS message bus not running | Check OVOS services: `docker compose ps` in the WASABI OVOS directory |
| Voice not responding | AVAROS skill container unhealthy | Restart: `docker compose -f docker/docker-compose.avaros.yml restart avaros_skill` |
| Wrong answer | Metric not mapped | Verify metric mapping covers the queried metric |
| "I don't understand" | Phrasing not recognized | Use exact phrases from the voice commands reference card |
| Intent disabled | Intent turned off in settings | Re-enable in Web UI → Settings → Intent Activation |

### Docker Service Issues

| Problem | Possible Cause | Resolution |
|---------|---------------|------------|
| Service shows `unhealthy` | Container failed to start | Check logs: `docker compose -f docker/docker-compose.avaros.yml logs <service>` |
| Database connection error | PostgreSQL not ready | Wait 30 seconds and check again — DB has a startup delay |
| Port already in use | Another service uses port 443/80 | Change `AVAROS_HTTPS_PORT` / `AVAROS_HTTP_PORT` in `.env` |
| Out of disk space | Logs or database grew | Clean old logs: `docker system prune` and check `docker/logs/` |
| TLS certificate error | Certificate expired or missing | Regenerate: `cd docker/nginx && ./generate-dev-cert.sh` |
| Browser shows certificate warning | Self-signed certificate | Expected for self-signed certs — click "Advanced" → "Proceed" |

### Web UI Issues

| Problem | Possible Cause | Resolution |
|---------|---------------|------------|
| 401 Unauthorized | API key not set or incorrect | Set `AVAROS_WEB_API_KEY` in `.env` or use the auto-generated key from logs |
| Blank page | Frontend build failed | Check web-ui container logs |
| Cannot access UI | Nginx proxy not running | Restart proxy: `docker compose -f docker/docker-compose.avaros.yml restart avaros-proxy` |

---

## 12. Rollback and Recovery

### Reset Configuration

To start fresh with the Web UI wizard:

1. Navigate to **Settings** in the Web UI
2. Click **Reset Platform Configuration**
3. The wizard will reappear on the next page load
4. Re-enter all configuration (platform, credentials, mappings)

Alternatively, via API:

```bash
curl -X DELETE https://localhost/api/v1/config/platform \
  -H "X-API-Key: <your-api-key>"
```

### Restore from Database Backup

The PostgreSQL database stores all configuration, baselines, and production data.

**Create a backup:**

```bash
docker exec avaros_db pg_dump -U avaros avaros > avaros_backup_$(date +%Y%m%d).sql
```

**Restore from backup:**

```bash
docker exec -i avaros_db psql -U avaros avaros < avaros_backup_YYYYMMDD.sql
```

> **Recommendation:** Schedule daily automatic backups using cron.

### Roll Back to a Previous Version

If an update causes problems:

```bash
# Stop current services
docker compose -f docker/docker-compose.avaros.yml down

# Check out the previous known-good version
git log --oneline -10   # Find the previous commit hash
git checkout <commit-hash>

# Rebuild and restart
docker compose -f docker/docker-compose.avaros.yml up -d --build
```

### Emergency Contacts

| Role | Contact | When to Use |
|------|---------|-------------|
| Lead Developer | Mohamad (AVAROS team) | System issues, configuration problems, software bugs |
| RENERYO Support | ArtiBilim operations | API connectivity, meter configuration, data quality |
| WASABI Coordinator | BIBA consortium | OVOS stack issues, experiment timeline questions |

---

## 13. Site-Specific Appendices

### Appendix A: ArtiBilim (Primary Pilot)

| Parameter | Value |
|-----------|-------|
| **Organization** | ArtiBilim A.Ş. |
| **Location** | Ankara, Turkey |
| **Industry** | Manufacturing (plastics/toy) |
| **Role** | Primary pilot site |
| **Infrastructure** | RENERYO-monitored factory with existing energy meters |

#### RENERYO Configuration

| Setting | Value |
|---------|-------|
| API URL | *(to be filled during M3–M4 coordination)* |
| Authentication type | Cookie-based |
| Known meters | *(to be filled after meter audit)* |

#### Asset Mapping

| AVAROS Asset Name | Physical Asset | RENERYO Meter ID |
|-------------------|---------------|-------------------|
| *(to be filled)* | *(to be filled)* | *(to be filled)* |

#### Production Data Source

| Parameter | Value |
|-----------|-------|
| Source system | *(ERP name or manual entry — to be confirmed)* |
| Export format | CSV |
| Upload frequency | Daily |
| Responsible person | *(to be assigned)* |

#### Site-Specific Notes

- ArtiBilim is the SME partner in the WASABI experiment
- RENERYO is already deployed and collecting energy data
- Production data integration method to be confirmed during M3–M4 coordination
- Emission factor: Turkey electricity grid (0.48 kg CO₂/kWh, verify current IEA data)

---

### Appendix B: MEXT Digital Factory (Secondary Pilot)

| Parameter | Value |
|-----------|-------|
| **Organization** | AI EDIH TÜRKIYE |
| **Location** | İstanbul, Turkey |
| **Industry** | Digital factory showroom (simulated manufacturing) |
| **Role** | Secondary pilot site |
| **Infrastructure** | Simulated manufacturing environment |

#### RENERYO Configuration

| Setting | Value |
|---------|-------|
| API URL | *(to be filled during M4 coordination)* |
| Authentication type | Cookie-based |
| Known meters | *(to be filled — may use simulated data)* |

#### Simulated Manufacturing Data

The MEXT Digital Factory is a showroom environment. Manufacturing data may be:
- Simulated using the AVAROS mock adapter
- Generated from the MEXT digital twin
- A mix of real sensor data and simulated production counts

| Parameter | Value |
|-----------|-------|
| Data approach | *(to be determined during M4 coordination)* |
| Simulation parameters | *(to be defined)* |

#### Site-Specific Notes

- MEXT is the Digital Innovation Hub partner
- Coordination for secondary pilot begins in M4 (May 2026)
- May use a combination of real energy data and simulated production data
- Focused on demonstrating AVAROS capabilities in a showroom context

---

## 14. Security and Privacy

### Data in Transit

All traffic between the browser and AVAROS is encrypted using HTTPS/TLS:
- TLS 1.2 and 1.3 supported
- Strong cipher suites enforced
- HTTP Strict Transport Security (HSTS) enabled
- HTTP requests automatically redirected to HTTPS

### Data at Rest

| Data Type | Storage | Protection |
|-----------|---------|------------|
| Platform API credentials | PostgreSQL | Fernet symmetric encryption |
| Metric mappings | PostgreSQL | Not encrypted (non-sensitive) |
| Production data | PostgreSQL | Not encrypted (non-personal) |
| KPI baselines | PostgreSQL | Not encrypted (non-personal) |

### GDPR Compliance

| Aspect | Status |
|--------|--------|
| Personal data processing | **None** — AVAROS processes manufacturing KPIs only |
| Voice audio | **Not retained** — OVOS processes speech locally, no recordings stored |
| User accounts | **None** — API key authentication, no personal accounts |
| Data deletion | Available via Web UI and API for all stored data |
| Data export | Anonymized KPI export available for D3.2 reporting |

### API Authentication

- All API endpoints (except `/health`) require an API key
- API key is sent via the `X-API-Key` HTTP header
- If no key is configured, a random key is generated on startup and logged
- **For production:** Always set an explicit `AVAROS_WEB_API_KEY` in the environment

### Data Retention

| Data | Retention | Deletion |
|------|-----------|----------|
| Platform configuration | Until manually deleted | Web UI or `DELETE /api/v1/config/platform` |
| Metric mappings | Until manually deleted | Web UI or `DELETE /api/v1/config/metrics/{name}` |
| Production records | Until manually deleted | Web UI delete function |
| KPI baselines | Until manually deleted | `DELETE /api/v1/kpi/baseline/{site_id}/{metric}` |
| Audit logs | Configurable | Automatic expiry based on retention setting |

### Security Recommendations for Production

1. Set a strong `AVAROS_WEB_API_KEY` (at least 32 characters)
2. Use Let's Encrypt for TLS certificates (not self-signed)
3. Restrict network access to the server (firewall rules)
4. Schedule regular database backups
5. Monitor Docker container health
6. Keep Docker images and dependencies updated
