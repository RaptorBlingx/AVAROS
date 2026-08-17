# AVAROS Verified End-User Query Catalogue

Tested: 2026-08-14 UTC

Active profile: `reneryo`

Configured production assets: `Line-1`, `Line-2`, `Line-3`

Tested path: AVAROS browser → HiveMind → OVOS → AVAROS → Reneryo

This is the current catalogue of natural-language queries verified through the live AVAROS browser path after the DIA quality overhaul. It includes useful data answers and deliberate clarifications/refusals where AVAROS must remain truthful.

Numeric values are snapshots of mutable Reneryo data. When validating a result, prioritize the metric, asset scope, requested period, aggregation, evidence card, and safety wording over an exact changing number.

## How to use this catalogue

1. Open AVAROS at `http://10.33.10.101:8080`.
2. Enter each query as written, using text or voice.
3. Check the concise headline and the evidence card.
4. For data responses, confirm the card contains metric, asset, value, unit, period, aggregation, sample count, source observation time, source profile, coverage/warnings, and query ID.

`last month` means the previous calendar month. `past 30 days` is a rolling period. A query without a period uses the latest available source observation and identifies its timestamp.

## 1. KPI, aggregation, and provenance

| Verified end-user query | Expected result |
|---|---|
| `What is the OEE for Line-1 last month?` | Full-period OEE `average`, not the first/oldest record. Live snapshot: `55.3%` from 1,681 observations. |
| `How much energy was consumed by Line-3 last month?` | Total energy using `sum`, not energy per unit. Live snapshot: about `17,493,260.6 kWh` from 1,681 observations. |
| `What is the energy per unit for Line-3 last month?` | Energy intensity using its own `average` calculation; distinct from total energy. |
| `What is the scrap rate for Line-2?` | Latest available scrap observation with source timestamp, not an implied live/current value. |
| `Show OEE and scrap rate for Line-2 over the past 30 days.` | Two separate KPI evidence rows for Line-2 and the rolling 30-day period. |
| `What was Line-1 OEE in July 2026?` | Named calendar-month result. Live snapshot: average `55.3%` from 1,681 observations. |
| `Show OEE for Line-1 from 2026-07-10 to 2026-07-12.` | Explicit no-data response for this live data snapshot; no fallback to another period. |

## 2. Factory scope, comparison, ranking, and trends

| Verified end-user query | Expected result |
|---|---|
| `Give me a factory summary for all lines last month.` | Nine evidence rows: OEE, throughput, and scrap for each of the three lines. Five live browser-path paraphrases had p95 `4.151 s`. |
| `Show a factory overview for all lines last month.` | Same complete nine-row summary scope as the factory-summary query. |
| `Compare OEE across all lines last month.` | All three values, requested period, `average` aggregation, and percentage-point wording. Live snapshot: Line-3 `56.8%`, Line-1 `55.3%`, Line-2 `52.6%`; spread `4.3 percentage points`. |
| `Rank all lines by OEE last month.` | Full ranking of every configured production line, with all values. |
| `What is the average OEE across all lines last month?` | All-line average plus each contributing line value. |
| `Show the OEE trend for Line-1 last month.` | Trend direction/change for the requested period with source points in the evidence card. |

## 3. Definitions, objectives, diagnosis, and advice

| Verified end-user query | Expected result |
|---|---|
| `What does OEE mean?` | OEE definition, formula, direction, and required data. It does not ask for an asset. |
| `Is OEE good on Line-1 last month?` | Observed value/trend plus an explicit statement that no objective is configured; no invented performance judgment. |
| `Why did OEE change on Line-1 last month?` | Evidence-aligned possible contributors only. AVAROS explicitly says it cannot establish a root cause and correlation is not proven causation. |
| `What do you recommend for scrap rate on Line-2 last month?` | Advisory inspection actions tied to the observed metric, not a machine-control instruction. |
| `What if scrap rate drops by 10 percent on Line-1?` | A valid bounded direct-KPI scenario with the calculation and stated assumption. |

## 4. Conversation follow-ups

Send this sequence in one browser conversation:

1. `What is the latest OEE for Line-1?`
2. `What about Line-2?`
3. `Compare them.`
4. `Why?`
5. `What does that mean?`

Verified behavior:

- Step 2 preserves OEE and changes the asset to Line-2.
- Step 3 compares both Line-1 and Line-2 with evidence for each.
- Step 4 uses the prior metric/context but retains the no-causality boundary.
- Step 5 explains the prior metric or result rather than losing the conversation context.

Other verified follow-ups: `And the scrap rate?` and `Use the same period.`

Conversation state is in memory only, bounded per browser session, and expires after 15 minutes. AVAROS does not persist the conversation text.

## 5. Status, active scope, and help

| Verified end-user query | Expected result |
|---|---|
| `Show system status.` | Operator-language Reneryo connectivity, active profile, data freshness, 3 configured assets, 19 mapped metrics, and PREVENTION availability. |
| `What is the active profile?` | Reports `reneryo` without irrelevant internal implementation details. |
| `List assets.` | Lists Line 1, Line 2, and Line 3. |
| `What can you do?` | Active capability list derived from the current profile; it does not advertise unavailable analytics or machine control. |
| `Rank suppliers by performance.` | Says no supplier assets are configured instead of treating production lines as suppliers. |

## 6. Honest boundaries and clarification

These are verified correct responses. A clarification/refusal is the expected result.

| Verified end-user query | Expected result |
|---|---|
| `Show OEE for Line-99.` | Says Line-99 is not configured and suggests Line 1, Line 2, and Line 3. |
| `Show OEE for Line-1 next month.` | Clarifies that the future period is unsupported. It does not silently use today or treat the request as a forecast. |
| `What is the energy cost for Line-1 last month?` | Says energy cost is not a configured canonical metric; it does not return energy per unit. |
| `Check all assets for anomalies.` | Says PREVENTION analytics are unavailable. It never reports fake “no anomalies” or fake successful check counts. |
| `Forecast OEE for Line-1 next week.` | Says PREVENTION forecasting is unavailable in the current profile. |
| `What if temperature drops by 10 degrees?` | Rejects the scenario because no process-to-KPI sensitivity model is configured. |
| `What if scrap rate drops by 200 percent?` | Rejects the physically impossible reduction instead of clamping it. |
| `Turn off Line-2.` | States AVAROS is read-only and cannot control equipment; no setting, equipment, or upstream control state is changed. |
| `purple banana calibration galaxy` | Returns a useful browser clarification with suggested manufacturing questions instead of silence or an unrelated KPI. |

## Current Reneryo-profile limitations

The following are intentionally unavailable until their required configuration exists:

- Supplier ranking: requires configured supplier assets.
- Objective-based “good/bad” judgment: requires a site or asset KPI objective.
- Anomaly, drift, forecast, and proactive alerts: require a healthy PREVENTION service.
- Process-parameter what-if calculations: require an approved sensitivity model.
- Machine controls: always unavailable from AVAROS because it is advisory and read-only.

## Related documents

- Detailed before/after test guide: [AVAROS-DIA-QUALITY-TEST-GUIDE.md](AVAROS-DIA-QUALITY-TEST-GUIDE.md)
- Findings, evidence, and regression coverage: [AVAROS-DIA-QUALITY-AUDIT.md](AVAROS-DIA-QUALITY-AUDIT.md)
