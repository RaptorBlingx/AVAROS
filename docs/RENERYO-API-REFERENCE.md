# Reneryo API Reference — AVAROS Source of Truth

> **Last verified:** 2026-03-12 by live API probe  
> **Base URL:** `http://deploys.int.arti.ac:31290/api`  
> **Swagger UI:** `http://deploys.int.arti.ac:31290/api/ui`  
> **Auth:** Session cookie `Cookie: S=<value>` (see `.env` → `RENERYO_SESSION_COOKIE`)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Metric CRUD](#2-metric-crud)
3. [Writing Values](#3-writing-values)
4. [Reading Values](#4-reading-values)
5. [SEU Endpoints](#5-seu-endpoints)
6. [Meter Endpoints](#6-meter-endpoints)
7. [Known Bugs & Workarounds](#7-known-bugs--workarounds)
8. [AVAROS Data Generator](#8-avaros-data-generator)
9. [Mapping File Format](#9-mapping-file-format)
10. [Quick Curl Examples](#10-quick-curl-examples)

---

## 1. Authentication

| Method | Header | Format |
|--------|--------|--------|
| Session Cookie | `Cookie` | `S=<uuid>.<signature>` |
| Bearer Token | `Authorization` | `Bearer <token>` (not yet provisioned) |

**Session cookie** is the only working auth method. Stored in `.env` as `RENERYO_SESSION_COOKIE` (URL-encoded — the `/` in the signature is `%2F`).

When making HTTP calls from Python, use the **decoded** cookie value:
```
S=97d7e08e-6cd9-4852-b2e2-b1dcb5d519e8.gwuuOksJCtXZYrexVjNiZCZY8hY8sgRPa5gtzkkkU/0=
```

**⚠ Common error:** `401 Unauthorized` — cookie expired or wrong format. Renew at Reneryo web UI.

---

## 2. Metric CRUD

### List Metrics

```
GET /u/measurement/metric/item?count=50
```

**Response (200):**
```json
{
  "recordCount": 36,
  "records": [
    {
      "id": "bdff7574-c443-4af0-8fa9-acf18026b3c6",
      "name": "AVAROS CO2 Per Batch",
      "type": "GAUGE",
      "unitGroup": "SCALAR",
      "description": "co2_per_batch (%)"
    }
  ]
}
```

**Notes:**
- Returns ALL metrics in the tenant (not just AVAROS ones)
- AVAROS metrics are prefixed with "AVAROS " (21 exist — 19 SCALAR + 2 legacy CURRENT duplicates)
- Filter for `unitGroup === "SCALAR"` to get the correct AVAROS metrics
- Legacy `CURRENT`-unit duplicates exist for `co2_total`, `energy_per_unit`, `oee` — **ignore these**

### Create Metric

```
POST /u/measurement/metric/item
Content-Type: application/json

{
  "name": "AVAROS Scrap Rate",
  "type": "GAUGE",
  "unitGroup": "SCALAR",
  "description": "scrap_rate (%)"
}
```

**Response (200):**
```json
{
  "id": "abc12345-...",
  "name": "AVAROS Scrap Rate",
  "type": "GAUGE",
  "unitGroup": "SCALAR"
}
```

**⚠ Common error:** `400` if metric with same name already exists.

### List Resources Under a Metric

```
GET /u/measurement/metric/resources?metricId=<metric_uuid>
```

**Response (200):**
```json
{
  "recordCount": 3,
  "records": [
    {
      "id": "7e74b6be-b6a0-471e-85c0-9f3ced9a6850",
      "metricId": "...",
      "unit": "SCALAR",
      "labels": [{"key": "line", "value": "Line-3"}]
    }
  ]
}
```

**Notes:**
- Each metric can have **multiple resources** (one per label combination)
- Resources are created automatically on first write
- The `labels` array on a resource tells you which asset the resource belongs to

---

## 3. Writing Values

### Write Endpoint

```
POST /u/measurement/metric/item/<metric_id>/values
Content-Type: application/json

{
  "unit": "SCALAR",
  "values": [
    {"value": 2.45, "datetime": "2026-03-12T06:00:00.000Z"},
    {"value": 2.51, "datetime": "2026-03-12T07:00:00.000Z"}
  ],
  "labels": [{"key": "line", "value": "Line-1"}]
}
```

**Response (200):**
```json
{
  "resourceId": "09881529-c1de-4135-bb9f-d564a58ad606"
}
```

### Label Rules (CRITICAL — avoids 500 errors)

| Scenario | Labels | Result |
|----------|--------|--------|
| **First write** with `[{"key":"line","value":"Line-1"}]` | Creates new resource | ✅ 200 |
| **First write** with `[]` (empty labels) | Creates new unlabeled resource | ✅ 200 |
| **Append** to unlabeled resource (`labels: []`) | Appends to existing | ✅ 200 |
| **Append** to labeled resource (`labels: [...]`) | **BUG: returns 500** | ❌ 500 |

**⚠ CRITICAL BUG:** Once a resource is created WITH labels, you CANNOT append to it. Reneryo returns `500 INTERNAL`. This is a server-side bug.

**Workaround for seeding:** Use labels on the initial write to create per-asset resources. For daemon/continuous writes, use `labels: []` which creates separate unlabeled resources (not ideal but works).

### Value Format

```json
{
  "value": 2.45,
  "datetime": "2026-03-12T06:00:00.000Z"
}
```

- `value`: float (not string)
- `datetime`: ISO 8601 with milliseconds and Z suffix
- Timestamps must be unique within a batch — duplicate timestamps in the same batch may cause `500`

### Unit Groups

| unit (in write payload) | Meaning |
|-------------------------|---------|
| `SCALAR` | Dimensionless (%, ratio, count) — **use for all AVAROS metrics** |
| `ENERGY` | kWh (Reneryo's native energy meters) |
| `CURRENT` | Amps — legacy, do NOT use |

---

## 4. Reading Values

### Read from Metric Resource

```
GET /u/measurement/metric/resource/<resource_id>/values
    ?period=DAILY
    &datetimeMin=2026-03-08T00:00:00Z
    &datetimeMax=2026-03-12T23:59:59Z
    &count=10
    &page=1
```

**Response (200):**
```json
{
  "recordCount": 3,
  "records": [
    {
      "sampleCount": 24,
      "value": 2.45,
      "datetime": "2026-03-10T00:00:00.000Z"
    },
    {
      "sampleCount": 8,
      "value": 2.51,
      "datetime": "2026-03-11T00:00:00.000Z"
    }
  ]
}
```

### Period Values

| Period | Aggregation |
|--------|-------------|
| `RAW` | No aggregation — individual data points |
| `MINUTELY` | Per-minute average |
| `HOURLY` | Per-hour average |
| `DAILY` | Per-day average |
| `WEEKLY` | Per-week average |
| `MONTHLY` | Per-month average |

### Pagination

- `count`: Max records per page (max 100)
- `page`: 1-based page number
- Response `recordCount` shows total matching records (not page size)

**⚠ Common error:** If `datetimeMin`/`datetimeMax` are missing, some endpoints return `400 BAD_REQUEST`.

---

## 5. SEU Endpoints

SEUs (Significant Energy Users) are Reneryo's built-in energy monitoring entities.

### List SEU Names

```
GET /u/measurement/seu/names
```

**Response (200):**
```json
{
  "recordCount": 4,
  "records": [
    {
      "id": "359a2b95-aa9f-4aa2-81e9-bcc16fb6a4d9",
      "name": "Seu",
      "energyResource": "ELECTRIC"
    },
    {
      "id": "d1cde463-cadb-4894-b1ed-e0cddec4a351",
      "name": "Seu Lorem Ipsum is simply dummy text",
      "energyResource": "GAS"
    },
    {
      "id": "d5fd2213-87f4-4f8a-99c0-9a14b1715a9e",
      "name": "Seu With Manually Selected Slice",
      "energyResource": "ELECTRIC"
    },
    {
      "id": "c5344063-bc63-4ef3-91fd-2d3de3ddbd02",
      "name": "Seu 4 for reporting",
      "energyResource": ""
    }
  ]
}
```

### List SEU Items

```
GET /u/measurement/seu/item
```

**⚠ Returns `400 BAD_REQUEST`** — Reneryo requires unknown parameters for this endpoint. **Use `/seu/names` instead.**

### Read SEU Values

```
GET /u/measurement/seu/item/<seu_id>/values
    ?datetimeMin=2026-03-01T00:00:00Z
    &datetimeMax=2026-03-12T23:59:59Z
    &period=DAILY
```

**Response (200):**
```json
{
  "recordCount": 10,
  "records": [
    {
      "value": 0.00123,
      "datetime": "2026-03-01T00:00:00.000Z"
    }
  ]
}
```

**Notes:**
- SEU values are **real energy data** from Reneryo's own monitoring — NOT our generated data
- Values are tiny (~0.001 kWh hourly) — this is real meter data, not test data
- Only 2 of 4 SEUs have data (Seu: 10 records, Seu Lorem: 5 records)
- SEU data uses the `value` field (not `consumption` or `production`)

---

## 6. Meter Endpoints

### List Meters

```
GET /u/measurement/meter/item
    ?datetimeMin=2025-01-01T00:00:00Z
    &datetimeMax=2026-12-31T23:59:59Z
```

**⚠ Requires `datetimeMin` and `datetimeMax` — without them returns empty or error.**

**Response (200):**
```json
{
  "recordCount": 6,
  "records": [
    {
      "id": "c95af779-...",
      "name": "Electric Main Meter"
    },
    {
      "id": "0cc56db9-...",
      "name": "Meter 1"
    }
  ]
}
```

**Known meters (as of 2026-03-12):**
- Electric Main Meter
- Meter 1, Meter 2, Meter 3
- Gas Main Meter
- (+ 1 more)

### Meter Names

```
GET /u/measurement/meter/names
```

Returns a simpler list of meter names.

---

## 7. Known Bugs & Workarounds

### BUG-001: Append to Labeled Resource → 500

**Problem:** Writing values to a resource that was created WITH labels returns `500 INTERNAL`.

**Reproduction:**
1. Write with `labels: [{"key":"line","value":"Line-1"}]` → 200 OK (creates resource)
2. Write again with same labels → **500 INTERNAL**

**Root cause:** Reneryo server bug — append to labeled resources fails.

**Fix (implemented 2026-03-12):** Switched to **per-asset metrics** with empty labels.
Instead of one "AVAROS Energy Per Unit" metric with labeled resources per asset,
we now create separate metrics: "AVAROS Energy Per Unit :: Line-1", ":: Line-2", etc.
Each metric has ONE unlabeled resource. Empty-label appends (`labels: []`) always succeed.

This gives us:
- 19 canonical metrics × 3 assets = **57 Reneryo metrics**
- All writes use `labels: []` — unlimited appends
- `mapping_output.json` maps `{metric_name: {asset: resource_id}}` as before

### BUG-002: SEU /item Returns 400

**Problem:** `GET /u/measurement/seu/item` returns `400 BAD_REQUEST` without additional parameters.

**Workaround:** Use `GET /u/measurement/seu/names` instead (returns the same data in a different format).

### BUG-003: Duplicate Metrics (SCALAR vs CURRENT)

**Problem:** Some metrics exist in both `unitGroup=SCALAR` and `unitGroup=CURRENT`: `co2_total`, `energy_per_unit`, `oee`.

**Workaround:** Always filter for `unitGroup === "SCALAR"` when listing AVAROS metrics. The `CURRENT` variants are leftovers from early testing.

---

## 8. AVAROS Data Generator

### Location

```
tools/reneryo-data-generator/generator.py
```

### Modes

| Mode | Command | Docker Env | Description |
|------|---------|------------|-------------|
| Seed | `python generator.py --seed` | `GENERATOR_MODE=seed` | Create metrics + write 90 days of history |
| Daemon | `python generator.py --daemon` | `GENERATOR_MODE=daemon` | Seed + push 1 value per metric per asset every 15 min |
| Verify | `python generator.py --verify` | `GENERATOR_MODE=verify` | Read back and print latest values |
| List | `python generator.py --list` | `GENERATOR_MODE=list` | Show metric→resource mapping table |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RENERYO_API_URL` | `http://deploys.int.arti.ac:31290/api` | Base URL |
| `RENERYO_SESSION_COOKIE` | (required) | Session cookie value without `S=` prefix |
| `GENERATOR_MODE` | `seed` | One of: seed, daemon, verify, list |
| `GENERATOR_INTERVAL` | `900` | Seconds between daemon writes |
| `GENERATOR_SEED_DAYS` | `90` | Days of historical data |
| `GENERATOR_BATCH_DELAY` | `100` | Milliseconds between batch writes |

### Docker Service

Defined in `docker/docker-compose.avaros.yml` as `avaros-data-generator`.

```yaml
avaros-data-generator:
  container_name: avaros-data-generator
  build:
    context: ../tools/reneryo-data-generator
    dockerfile: Dockerfile.generator
  environment:
    - RENERYO_API_URL=${RENERYO_API_URL}
    - RENERYO_SESSION_COOKIE=${RENERYO_SESSION_COOKIE}
    - GENERATOR_MODE=daemon
    - GENERATOR_INTERVAL=900
    - GENERATOR_SEED_DAYS=90
    - GENERATOR_BATCH_DELAY=100
```

### Current State (2026-03-12)

- **Generator container is RUNNING** in daemon mode (seeding 90 days + continuous push every 15 min)
- **Per-asset metrics:** 57 metrics created (19 canonical × 3 assets), format: "AVAROS Energy Per Unit :: Line-1"
- **All writes use `labels: []`** — no more 500 errors
- **Daemon appends work indefinitely** — each write goes to the same unlabeled resource per metric
- **Old labeled resources still exist** from prior seeding — they have stale data but are no longer used

### Assets Generated

| Asset | Metrics |
|-------|---------|
| Line-1 | All 19 |
| Line-2 | All 19 |
| Line-3 | All 19 |

---

## 9. Mapping File Format

**File:** `tools/reneryo-data-generator/mapping_output.json`

```json
{
  "energy_per_unit": {
    "Line-1": "09881529-c1de-4135-bb9f-d564a58ad606",
    "Line-2": "67afbdf6-1861-4bd4-b9b7-5887e031981f",
    "Line-3": "7e74b6be-b6a0-471e-85c0-9f3ced9a6850"
  },
  "scrap_rate": {
    "Line-1": "2f80230e-df7e-449f-baaf-c15e34974b57",
    "Line-2": "3b34cdf1-0862-4e0f-a0b6-17611d64168e"
  }
}
```

**Format:** `{canonical_metric_name: {asset_display_name: reneryo_resource_uuid}}`

**Import into AVAROS:** `POST /api/v1/assets/import-generator-mapping` with body `{"mapping": <content>}`

---

## 10. Wizard Configuration Guide

Use this section when configuring AVAROS for RENERYO through the unified wizard. Fill in the exact values for each step.

### Step 1 — Connect

| Field | Value |
|-------|-------|
| API URL | `http://deploys.int.arti.ac:31290/api` (or your RENERYO base URL) |
| Auth type | Cookie |
| API key / Cookie | Session cookie value from `.env` → `RENERYO_SESSION_COOKIE` |

### Step 2 — Register Assets

Register these assets (ID = display name for RENERYO):

| Asset ID | Display Name | Type |
|----------|--------------|------|
| Line-1 | Line 1 | line |
| Line-2 | Line 2 | line |
| Line-3 | Line 3 | line |

### Step 3 — Map Metrics

For each metric × asset combination, use the endpoint template and resource UUID from `mapping_output.json`. The endpoint uses `{asset_id}` placeholder — the wizard substitutes the asset ID (e.g. `Line-1`).

**Endpoint template:** `/u/measurement/metric/resource/{resource_id}/values?period=RAW&count=1`  
**JSONPath (latest value):** `$.records[-1].value`  
**JSONPath (trend):** `$.records`

| Metric | Unit | Line-1 Resource UUID | Line-2 Resource UUID | Line-3 Resource UUID |
|--------|------|---------------------|---------------------|---------------------|
| energy_per_unit | kWh/unit | 09881529-c1de-4135-bb9f-d564a58ad606 | 67afbdf6-1861-4bd4-b9b7-5887e031981f | 7e74b6be-b6a0-471e-85c0-9f3ced9a6850 |
| energy_total | kWh | 292e9098-45e4-43df-8a49-5f952e57047c | 502eb30b-4d08-44dd-ada1-2f17db80a83b | 4ccbe92b-9d0b-4f40-bfa6-9e4585dfe1b9 |
| peak_demand | kW | dbb8a24e-ec1d-470d-ad66-7cfd5770683b | d18a1ddd-13ec-4769-b6e9-317c03a6b776 | 52a93867-2126-4e6a-b70e-272e1e8eb559 |
| peak_tariff_exposure | % | 6f8320a7-6b1e-468a-b328-1eab39e667c5 | f94d55e9-c673-4dcf-b62e-c8ee35b4f7e8 | 4aa1e468-86c9-47b4-bc4b-1c03929d53fa |
| scrap_rate | % | 2f80230e-df7e-449f-baaf-c15e34974b57 | 3b34cdf1-0862-4e0f-a0b6-17611d64168e | — |
| rework_rate | % | b57c52b5-cf70-4afe-80a4-d15ef5eb9c56 | af613087-836e-4d01-8f29-764fde05ecd8 | — |
| material_efficiency | % | ac894e3e-5537-4fd3-b483-9518060760ed | 04a25d72-163b-4104-9fc3-9f03426d1bc8 | — |
| recycled_content | % | eb1331f2-27cf-4812-85a8-8340f823a114 | c68bb89a-b341-4c77-906a-798103a549e9 | — |
| oee | % | fb34799f-11ba-4319-94e0-e9e380edb937 | 13f9a2c3-647a-4158-a283-3fe63e01b3b9 | — |
| throughput | units/hr | 7bfe59da-76e4-4425-992a-e01866e4ce94 | b61c5a08-23d5-4703-a754-d615d4379ab6 | — |
| cycle_time | sec | 5d9ffa66-a8d0-44c1-a2c8-726b3e5821ab | a8c75ef2-319b-4a57-8496-ddb46ea9677f | — |
| changeover_time | min | 5358b4c9-5729-42a8-9d0a-0a89814dd9f6 | 8d34c1e7-f360-4d34-b56c-5157f0cc5588 | — |
| co2_per_unit | kg CO₂-eq/unit | c9a4bfe8-6838-43ae-943d-0b89e509532d | 5fb3da2f-3637-4a95-84c2-cb3c18a2f526 | — |
| co2_total | kg CO₂-eq | d1ac87b6-01c9-49b9-885e-d4b71ca6ac2e | 521bb97d-1615-4aeb-9ae1-b52c6746b78d | — |
| co2_per_batch | kg CO₂-eq/batch | a9068f7d-087d-4cfe-913c-3caa564a0ef4 | 4dc4f13b-f27e-4cda-b560-8a6c1845d500 | — |
| supplier_lead_time | days | a453884f-a751-4169-8c08-153c9742c1ea | e4a488ca-3990-4973-8762-38b61198df18 | — |
| supplier_defect_rate | % | 3dc67069-0497-496c-9072-68793864d217 | 942f05b5-8cee-41f4-838e-2330a3618794 | — |
| supplier_on_time | % | fd74b87e-8a4b-4af0-9e0c-3c5bf8823cad | d3bde3fa-a416-4b1f-8811-7e45febd8baa | — |
| supplier_co2_per_kg | kg CO₂/kg | c974d385-ce5a-4504-bc2f-bda12f1825c4 | ad7a7c55-19b3-4e19-9a57-7bf8d8194933 | — |

**Per-metric wizard entry:** For each row, create one mapping per asset. Example for `energy_per_unit` on Line-1:
- Endpoint: `/u/measurement/metric/resource/09881529-c1de-4135-bb9f-d564a58ad606/values?period=RAW&count=1`
- JSONPath: `$.records[-1].value`
- Unit: `kWh/unit`

### Step 4 — Activate Intents

Enable the 19 KPI intents. Configure action intent bindings (control.turn_on, control.turn_off) if your RENERYO instance exposes control endpoints.

### Troubleshooting

- **BUG-001:** Labeled resource append returns 500 — use empty labels for daemon writes.
- **BUG-002:** Duplicate timestamps in batch may cause 500 — ensure unique datetimes.
- **BUG-003:** Cookie expiry — renew session at RENERYO web UI if 401 occurs.

---

## 11. Quick Curl Examples

### Auth Test
```bash
curl -s -H "Cookie: S=<cookie>" \
  "http://deploys.int.arti.ac:31290/api/u/measurement/metric/item?count=5" | python3 -m json.tool
```

### Read Latest Daily Values
```bash
curl -s -H "Cookie: S=<cookie>" \
  "http://deploys.int.arti.ac:31290/api/u/measurement/metric/resource/<resource_id>/values?period=DAILY&datetimeMin=2026-03-10T00:00:00Z&datetimeMax=2026-03-12T23:59:59Z&count=10" | python3 -m json.tool
```

### Write a Single Value
```bash
curl -s -X POST -H "Cookie: S=<cookie>" -H "Content-Type: application/json" \
  "http://deploys.int.arti.ac:31290/api/u/measurement/metric/item/<metric_id>/values" \
  -d '{"unit":"SCALAR","values":[{"value":42.5,"datetime":"2026-03-12T12:00:00.000Z"}],"labels":[]}' | python3 -m json.tool
```

### List SEUs
```bash
curl -s -H "Cookie: S=<cookie>" \
  "http://deploys.int.arti.ac:31290/api/u/measurement/seu/names" | python3 -m json.tool
```

### List Meters
```bash
curl -s -H "Cookie: S=<cookie>" \
  "http://deploys.int.arti.ac:31290/api/u/measurement/meter/item?datetimeMin=2025-01-01T00:00:00Z&datetimeMax=2026-12-31T23:59:59Z" | python3 -m json.tool
```

---

## Appendix: AVAROS Per-Asset Metric Naming

Metrics follow the pattern: `AVAROS {Display Name} :: {Asset}`

| Canonical Name | Reneryo Metric Name Pattern |
|---------------|---------------------------|
| energy_per_unit | AVAROS Energy Per Unit :: Line-1 / Line-2 / Line-3 |
| energy_total | AVAROS Energy Total :: Line-1 / Line-2 / Line-3 |
| oee | AVAROS OEE :: Line-1 / Line-2 / Line-3 |
| scrap_rate | AVAROS Scrap Rate :: Line-1 / Line-2 / Line-3 |
| ... | (19 canonical metrics × 3 assets = 57 total) |

> Run `python3 tools/reneryo-data-generator/generator.py --list` for the complete live mapping table.
> Mapping file: `tools/reneryo-data-generator/mapping_output.json`
