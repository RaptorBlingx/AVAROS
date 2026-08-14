# AVAROS DIA Quality Overhaul — What Changed and How to Test

Branch: `huge-avaros-fixing-session`

Use this guide to test the new AVAROS behavior as an operator or team lead. AVAROS remains deterministic, advisory, and read-only. It reads Reneryo data but does not change Reneryo or control production equipment.

## Where to test

1. Open the AVAROS browser interface at `http://10.33.10.101:8080` if you are on the server network.
2. Start or continue a browser conversation.
3. Send the queries below through text input or voice.
4. Read both the short spoken/text headline and the evidence card underneath it.

Reneryo remains available at:

- Frontend: `http://10.33.10.101:5173`
- Backend: `http://10.33.10.101:3000`

Numbers below are examples from the 2026-08-14 test data. They may change as Reneryo data changes; the important checks are the metric, asset, period, aggregation, evidence, and safety wording.

## Main improvements: before and after

| Area | Before | After | How to verify |
|---|---|---|---|
| Historical KPIs | AVAROS could use the oldest record in a period. | It fetches every Reneryo page and aggregates the full requested period. | Ask `What is the OEE for Line-1 last month?` and inspect `average`, period, sample count, and timestamps. |
| Total energy | “Energy consumed” could mean energy per unit. | It resolves total energy and uses `sum`; energy per unit remains a separate metric. | Ask `How much energy was consumed by Line-3 last month?` then `What is the energy per unit for Line-3 last month?` |
| Unknown assets | An unknown line could silently become Line-1. | It refuses the unknown asset and lists configured alternatives. | Ask `Show OEE for Line-99.` |
| Periods | Unsupported/future periods could be ignored or replaced. | Previous calendar month, rolling 30 days, named months, and explicit dates work; unsupported/future periods clarify. | Ask `What was Line-1 OEE in July 2026?` and `Show OEE for Line-1 next month.` |
| Multiple assets/KPIs | Questions often returned only one asset or one KPI. | AVAROS retains all mentioned assets and metrics. | Ask `Show OEE and scrap rate for Line-2 over the past 30 days.` |
| Comparisons | Responses could omit values/context and misuse `%`. | All values, period, aggregation, and `percentage points` are included. | Ask `Compare OEE across all lines last month.` |
| Factory summary | There was no useful all-line overview. | AVAROS returns OEE, throughput, and scrap for every configured line. | Ask `Give me a factory summary for all lines last month.` |
| Definitions | “What does OEE mean?” could be treated as a KPI query. | Definitions include formula, direction, unit, and data requirements. | Ask `What does OEE mean?` |
| Targets | “Is OEE good?” could imply a made-up target. | AVAROS uses a configured objective only; otherwise it says no objective is configured. | Ask `Is OEE good on Line-1 last month?` |
| Diagnosis | “Why?” could imply a root cause. | It gives evidence/possible contributors and says correlation is not proven causation. | Ask `Why did OEE change on Line-1 last month?` |
| Recommendations | Advice could be unrelated to the question. | Advice follows metric-specific, advisory inspection playbooks. | Ask `What do you recommend for scrap rate on Line-2 last month?` |
| Conversation context | Follow-ups failed or used unsafe defaults. | The browser retains structured context for 15 minutes. | Run the multi-turn test below in one conversation. |
| Anomaly/forecast claims | Disabled PREVENTION could still produce fake success. | AVAROS says analytics are unavailable when PREVENTION is unavailable. | Ask `Check all assets for anomalies.` |
| What-if scenarios | Temperature and impossible changes could produce misleading calculations. | Only direct, physically valid KPI scenarios are accepted. | Run the what-if boundary tests below. |
| Controls | AVAROS could imply it powered equipment on/off. | It explicitly refuses machine controls. | Ask `Turn off Line-2.` |
| Status/help | Responses were static and technical. | Status reports Reneryo connectivity/freshness; help uses the active capability manifest. | Ask `Show system status.` and `What can you do?` |
| Browser evidence | Users received only speech/text. | Browser responses include an evidence card with provenance and follow-up suggestions. | Run any KPI or comparison query and inspect the card. |

## Core acceptance tests

Run these one at a time. Each should give a direct, informative answer and an evidence card.

| Test query | What a correct result looks like |
|---|---|
| `What is the OEE for Line-1 last month?` | OEE for Line-1 using an `average` over the previous calendar month; card shows sample count and source time range. |
| `How much energy was consumed by Line-3 last month?` | Total energy using `sum`, not energy per unit. The live snapshot was about `17,493,260.6 kWh` from 1,681 observations. |
| `What is the energy per unit for Line-3 last month?` | Energy intensity, normally using `average`; distinct unit and value from total energy. |
| `Show OEE and scrap rate for Line-2 over the past 30 days.` | Two evidence rows: one OEE and one scrap-rate result for Line-2. |
| `What was Line-1 OEE in July 2026?` | A named calendar-month result; no fallback to today. |
| `Show OEE for Line-1 from 2026-07-10 to 2026-07-12.` | An honest no-data response if that range has no records; it must not substitute another date range. |
| `Give me a factory summary for all lines last month.` | Nine evidence rows: OEE, throughput, and scrap for Line-1, Line-2, and Line-3. |
| `Compare OEE across all lines last month.` | Every line's value plus average/period. Differences between percentages use `percentage points`. |
| `Rank all lines by OEE last month.` | A complete ranking, not just the best line. |
| `What is the average OEE across all lines last month?` | The all-line average plus the contributing values. |
| `Show the OEE trend for Line-1 last month.` | Direction/change and source evidence for the requested period. |

## Meaning, decision support, and objectives

| Test query | Expected behavior |
|---|---|
| `What does OEE mean?` | Definition, formula, higher/lower direction, and required inputs. It should not request an asset. |
| `Is OEE good on Line-1 last month?` | If no objective exists, reports the observed value/trend and explicitly says no objective is configured. |
| `Why did OEE change on Line-1 last month?` | Says it cannot establish a root cause from KPI observations alone; any contributors are described as possible, not proven causes. |
| `What do you recommend for scrap rate on Line-2 last month?` | Advisory inspection actions tied to the observed scrap result; no equipment command. |
| `What if scrap rate drops by 10 percent on Line-1?` | A bounded direct-KPI scenario with the calculation and assumption shown. |

## Conversation test

Use one browser conversation and send these messages in order:

1. `What is the latest OEE for Line-1?`
2. `What about Line-2?`
3. `Compare them.`
4. `Why?`
5. `What does that mean?`

Expected behavior:

- Step 2 keeps OEE and changes only the asset to Line-2.
- Step 3 compares Line-1 and Line-2, showing both values.
- Step 4 gives an evidence-based diagnosis boundary, not a claimed root cause.
- Step 5 explains the prior metric/result rather than losing context.

Other supported follow-ups include `And the scrap rate?` and `Use the same period.`

## Safety and honesty tests

These are especially important. A safe clarification/refusal is the correct result.

| Test query | Correct result |
|---|---|
| `Show OEE for Line-99.` | Says Line-99 is not configured and suggests Line 1, Line 2, and Line 3. |
| `Show OEE for Line-1 next month.` | Clarifies that the future period is unsupported; it must not silently treat it as a forecast or use today. |
| `What is the energy cost for Line-1 last month?` | Says energy cost is not configured; it must not return energy per unit. |
| `Check all assets for anomalies.` | Says PREVENTION analytics are unavailable in the current Reneryo profile. It must not say “no anomalies” or report fake check counts. |
| `Forecast OEE for Line-1 next week.` | Says forecasting is unavailable while PREVENTION is unavailable. |
| `What if temperature drops by 10 degrees?` | Rejects the request because no temperature-to-KPI model is configured. |
| `What if scrap rate drops by 200 percent?` | Rejects the physically impossible reduction; it must not clamp it and continue. |
| `Turn off Line-2.` | Says AVAROS is read-only and cannot control equipment. |
| `purple banana calibration galaxy` | Returns a helpful browser clarification instead of silence or an unrelated KPI. |
| `Rank suppliers by performance.` | Says no supplier assets are configured; it must not rank production lines as suppliers. |

## What to inspect in an evidence card

For KPI, comparison, trend, summary, and diagnostic responses, check that the card includes:

- Response type and query ID
- Requested period and aggregation method
- Metric, asset, value, and unit for each evidence row
- Source observation time/range and sample count
- Source profile (`reneryo`)
- Data-quality warnings or assumptions, when applicable
- Suggested follow-up questions

The spoken response should remain short. The evidence card is the detailed, inspectable proof behind it.

## Expected current profile boundaries

The active Reneryo profile has three production lines and 19 mapped metrics. It currently has no configured supplier assets, no configured OEE objective, and no available PREVENTION analytics endpoint. Therefore, the following answers are intentionally unavailable or bounded:

- Supplier rankings: unavailable until supplier assets are configured
- “Good/bad” performance judgment: unavailable until a site/asset objective is configured
- Anomaly, drift, forecast, and proactive alerts: unavailable until PREVENTION is configured and healthy
- Process-parameter what-ifs: unavailable until an approved sensitivity model is configured
- Equipment controls: always unavailable from AVAROS because it is read-only

## If a test fails

Record the exact query, time, browser session, spoken response, and the evidence-card query ID. Then compare it with the expected behavior in this guide and the tracked findings in [AVAROS-DIA-QUALITY-AUDIT.md](AVAROS-DIA-QUALITY-AUDIT.md).

For the concise list of only verified working queries, use [AVAROS-VERIFIED-END-USER-QUERIES.md](AVAROS-VERIFIED-END-USER-QUERIES.md).
