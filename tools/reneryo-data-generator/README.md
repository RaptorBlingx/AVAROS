# Mock RENERYO HTTP Server

A lightweight FastAPI mock that serves all 19 KPI endpoints from `ReneryoAdapter._ENDPOINT_MAP` with deterministic manufacturing data. This is a **development tool** for testing the RENERYO HTTP client pipeline without real API credentials.

## Quick Start (Local)

```bash
cd tools/reneryo-mock
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8090
```

Health check: `http://localhost:8090/health`

## Quick Start (Docker)

From the project root:

```bash
docker compose -f docker/docker-compose.avaros.yml up reneryo-mock -d
```

The server is available at `http://localhost:8090` (host) or `http://reneryo-mock:8090` (from other containers on the `ovos` network).

## Endpoints

### Health (no auth)

```
GET /health → {"status": "ok", "service": "reneryo-mock", "endpoints": 19}
```

### Canonical KPI Endpoints (auth required)

All 19 endpoints from `ReneryoAdapter._ENDPOINT_MAP`:

| Path | Metric |
|------|--------|
| `/api/v1/kpis/energy/per-unit` | `energy_per_unit` |
| `/api/v1/kpis/energy/total` | `energy_total` |
| `/api/v1/kpis/energy/peak-demand` | `peak_demand` |
| `/api/v1/kpis/energy/tariff-exposure` | `peak_tariff_exposure` |
| `/api/v1/kpis/material/scrap-rate` | `scrap_rate` |
| `/api/v1/kpis/material/rework-rate` | `rework_rate` |
| `/api/v1/kpis/material/efficiency` | `material_efficiency` |
| `/api/v1/kpis/material/recycled-content` | `recycled_content` |
| `/api/v1/kpis/supplier/lead-time` | `supplier_lead_time` |
| `/api/v1/kpis/supplier/defect-rate` | `supplier_defect_rate` |
| `/api/v1/kpis/supplier/on-time` | `supplier_on_time` |
| `/api/v1/kpis/supplier/co2-per-kg` | `supplier_co2_per_kg` |
| `/api/v1/kpis/production/oee` | `oee` |
| `/api/v1/kpis/production/throughput` | `throughput` |
| `/api/v1/kpis/production/cycle-time` | `cycle_time` |
| `/api/v1/kpis/production/changeover-time` | `changeover_time` |
| `/api/v1/kpis/carbon/per-unit` | `co2_per_unit` |
| `/api/v1/kpis/carbon/total` | `co2_total` |
| `/api/v1/kpis/carbon/per-batch` | `co2_per_batch` |

### Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `period` | Time period label | `today`, `last_7_days` |
| `asset_id` | Single asset ID | `Line-1` |
| `asset_ids` | Comma-separated IDs (comparison mode) | `Line-1,Line-2,Line-3` |
| `granularity` | Trend mode: `hourly`, `daily`, `weekly` | `daily` |
| `datetimeMin` | ISO start timestamp | `2026-02-01T00:00:00Z` |
| `datetimeMax` | ISO end timestamp | `2026-02-10T00:00:00Z` |
| `delay_ms` | Artificial latency in ms (for timeout testing) | `500` |

### Authentication

Any of these work:
- `Authorization: Bearer any-token-here`
- `Cookie: S=any-session-value`

No auth → HTTP 401.

### Native Reneryo Format

```
GET /api/u/measurement/meter/item?metric=energy_per_unit&meter=Line-1
```

Returns Reneryo's native measurement array format for testing the response-parsing layer.

## Examples

```bash
# Single KPI
curl -H "Authorization: Bearer test" http://localhost:8090/api/v1/kpis/energy/per-unit

# Trend
curl -H "Authorization: Bearer test" "http://localhost:8090/api/v1/kpis/energy/per-unit?granularity=daily"

# Comparison
curl -H "Authorization: Bearer test" "http://localhost:8090/api/v1/kpis/production/oee?asset_ids=Line-1,Line-2,Line-3"

# Native format
curl -H "Authorization: Bearer test" "http://localhost:8090/api/u/measurement/meter/item?metric=energy_per_unit"

# Test timeout handling
curl -H "Authorization: Bearer test" "http://localhost:8090/api/v1/kpis/energy/per-unit?delay_ms=2000"
```

## Data Characteristics

- Deterministic: seed-based `random.Random(42)` — same request → same data
- Value ranges match `MockAdapter._METRIC_BASELINES` in the skill codebase
- Trend data uses realistic random-walk with configurable granularity

---

# Reneryo Data Generator — Operator Runbook

The generator (`generator.py`) seeds and continuously feeds realistic manufacturing data into a **real Reneryo instance** for all 19 AVAROS canonical metrics. This is NOT the mock server — it writes to live Reneryo API.

## Prerequisites

1. **Reneryo access** — A running Reneryo instance with API access
2. **Session cookie** — Log into Reneryo in a browser, then copy the session cookie value from DevTools (Application → Cookies → `S` cookie)
3. **Python 3.10+** with dependencies installed

## Installation

```bash
cd tools/reneryo-mock
pip install -r requirements.txt
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RENERYO_API_URL` | No | `http://deploys.int.arti.ac:31290/api` | Reneryo API base URL |
| `RENERYO_SESSION_COOKIE` | **Yes** | — | Session cookie from browser |
| `GENERATOR_SEED_DAYS` | No | `90` | Days of historical data to create |
| `GENERATOR_INTERVAL` | No | `900` | Seconds between daemon writes |
| `GENERATOR_BATCH_DELAY` | No | `100` | Milliseconds between API batches |

## Usage

### 1. Seed Historical Data (First Run)

Creates all 19 metric resources in Reneryo and writes 90 days of historical data:

```bash
export RENERYO_SESSION_COOKIE="your-cookie-value"

# Seed with default 90 days of history
python3 generator.py --seed

# Seed with custom history depth
GENERATOR_SEED_DAYS=30 python3 generator.py --seed
```

Output: `mapping_output.json` — contains `{metric_name: {asset_id: resource_id}}` mapping.

### 2. Verify Data Was Written

Read back latest values and confirm data exists:

```bash
python3 generator.py --verify
```

### 3. Run as Daemon (Continuous Data)

After seeding, keep writing fresh data every 15 minutes:

```bash
python3 generator.py --daemon

# Custom interval (5 minutes)
GENERATOR_INTERVAL=300 python3 generator.py --daemon
```

### 4. List Current Mapping

Show the metric → resource ID mapping table:

```bash
python3 generator.py --list
```

### 5. Run via Docker Compose

```bash
# From project root
docker compose -f docker/docker-compose.avaros.yml up reneryo-generator -d

# Check logs
docker compose -f docker/docker-compose.avaros.yml logs reneryo-generator -f
```

## Configure AVAROS with Generator Output

After seeding, import the mapping into AVAROS so the adapter knows which resource ID to read for each metric:

```bash
# Option A: Import via API (recommended)
curl -X POST http://localhost:8080/api/v1/assets/import-generator-mapping \
  -H "X-API-Key: $AVAROS_WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json; print(json.dumps({"mapping": json.load(open("mapping_output.json"))}))')"

# Option B: Use the existing PUT endpoint manually
# Transform mapping_output.json to per-asset format and PUT to /api/v1/assets/mappings
```

## Validate the Full Pipeline

After seeding + importing mapping:

```bash
# From project root
python3 scripts/validate-metric-pipeline.py
```

This tests `get_kpi`, `get_trend`, `compare`, and `get_raw_data` for all 19 metrics.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Session cookie expired | Log into Reneryo browser UI → copy fresh cookie |
| `409 Conflict` or duplicate timestamps | Re-running seed on existing data | Delete metrics in Reneryo first, or skip — generator handles duplicates gracefully |
| `ConnectionError` | Reneryo not reachable | Check `RENERYO_API_URL` and network access |
| `mapping_output.json not found` | Daemon started before seed | Run `--seed` first to create metrics |
| Stale data in AVAROS | Mapping not imported | Re-import mapping via API (see above) |

## Directory Structure

```
tools/reneryo-mock/
├── generator.py          # Main generator script (seed/daemon/verify/list)
├── patterns.py           # Metric profiles, baselines, data generation patterns
├── reneryo_client.py     # Low-level Reneryo API client
├── data.py               # Data generation helpers
├── main.py               # Mock HTTP server (separate tool)
├── mapping_output.json   # RUNTIME OUTPUT — generated by --seed
├── requirements.txt      # Python dependencies
├── Dockerfile            # Mock server container
├── Dockerfile.generator  # Generator container
└── tests/                # Generator unit tests
```
