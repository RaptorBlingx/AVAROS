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
