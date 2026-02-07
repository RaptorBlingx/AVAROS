---
applyTo: "**/data/**,**/ingestion/**,**/connectors/**"
---
# Open Data Formats & Integration Rules

## 🎯 Proposal Commitment (Section 1.3)
"Data portability will be enforced through open exchange formats and interfaces"

## Supported Formats

### REST/JSON (Primary API Communication)
\`\`\`python
# All adapter responses as JSON
Content-Type: application/json

# Versioned schemas
{
    "schema_version": "1.0",
    "data": {...}
}
\`\`\`

### CSV/Parquet (Batch Data Import/Export)
- Supplier declarations: CSV with standard headers
- Historical time-series: Parquet (columnar, efficient)
- KPI exports: CSV for user download

### MQTT (Real-time Sensor Data)
\`\`\`
Topic: avaros/{site_id}/{asset_id}/{metric}
Payload: {"value": 42.5, "timestamp": "2026-01-29T10:00:00Z", "unit": "kWh"}
\`\`\`

### OPC-UA (Industrial Equipment)
- Use asyncua library for Python
- Map OPC-UA nodes to CanonicalMetric
- Bridge via MQTT for consistency

## Data Ingestion Architecture
\`\`\`
ERP/MES ──REST/JSON──┐
                      ├──► ETL Layer ──► RENERYO ──► AVAROS Adapter
Sensors ──MQTT───────┤
                      │
Suppliers ──CSV──────┘
\`\`\`

## Schema Standards

### Time-Series Data
\`\`\`json
{
    "asset_id": "compressor-1",
    "metric": "energy_per_unit",
    "timestamp": "2026-01-29T10:00:00Z",
    "value": 3.45,
    "unit": "kWh/unit",
    "quality": "GOOD"
}
\`\`\`

### Supplier Declaration
\`\`\`csv
supplier_id,material,lead_time_days,defect_rate_pct,co2_per_kg,timestamp
SUP-001,PET,14,0.5,2.1,2026-01-15
SUP-002,ABS,21,1.2,3.4,2026-01-15
\`\`\`

### Batch/Lot Data
\`\`\`json
{
    "batch_id": "B-2026-0129-001",
    "product": "Toy-A",
    "quantity": 1000,
    "start_time": "2026-01-29T06:00:00Z",
    "end_time": "2026-01-29T10:00:00Z",
    "energy_kwh": 450,
    "scrap_units": 12,
    "material_kg": 85
}
\`\`\`

## Integration Rules
1. NEVER use proprietary file formats
2. Document all schemas in \`schemas/\` folder
3. Version schemas (breaking changes = major version bump)
4. Validate incoming data against schema
5. Log schema validation failures
