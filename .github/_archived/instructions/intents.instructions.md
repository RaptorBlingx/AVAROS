---
applyTo: "**/locale/**/*.intent,**/locale/**/*.dialog"
---
# OVOS Intent and Dialog Rules

## 🎯 Intent Design Principle
Intents represent **manufacturing questions**, NOT API calls.  
Every intent maps to one of the **5 Query Types**.

## Naming Convention (MANDATORY)
Pattern: `{query_type}.{domain}.{detail}.intent`

| Query Type | Example Intent | Example Utterance |
|------------|---------------|-------------------|
| kpi | `kpi.energy.per_unit.intent` | "What's our energy per unit?" |
| compare | `compare.supplier.performance.intent` | "Compare Supplier A and B" |
| trend | `trend.scrap.monthly.intent` | "Show scrap trend last 3 months" |
| anomaly | `anomaly.production.check.intent` | "Any unusual patterns today?" |
| whatif | `whatif.material.substitute.intent` | "What if we use recycled plastic?" |

## Intent Files (.intent)
- One intent per file
- Include 10-20 sample utterances minimum
- Use manufacturing-domain slots (see below)
- Include variations: questions, commands, different phrasings
- Support synonyms inline: `(energy|power|electricity) for {asset}`

## Dialog Files (.dialog)
Pattern: `{query_type}.{domain}.response.dialog` / `.error.dialog`
- Multiple response variations (3-5 minimum)
- Use template variables: `{asset_name}`, `{value}`, `{unit}`, `{period}`
- Keep responses natural and conversational
- Include error/fallback dialogs for each intent

## Canonical Slots (Manufacturing Vocabulary)
| Slot | Maps To | Examples |
|------|---------|----------|
| {metric} | CanonicalMetric enum | energy_per_unit, scrap_rate, oee |
| {asset} | Machine/line identifier | Compressor-1, Line-A, Boiler-3 |
| {period} | TimePeriod | today, this week, last month, Q2 |
| {supplier} | Supplier identifier | Acme Corp, supplier-42 |
| {material} | Material type | steel, plastic, aluminum |
| {granularity} | Aggregation level | hourly, daily, weekly, monthly |

## Language Support
- Primary: en-us
- Structure: `locale/{lang}/{query_type}.{domain}.{detail}.intent`
