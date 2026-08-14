# AVAROS Capability Test Report

Date: 2026-08-13 UTC  
Deployment commit: `e131a6a`  
Active profile: `reneryo`  
Platform: `custom_rest` using session-cookie authentication  
API key: intentionally configured as `changeme`, per operator request

## Executive summary

The live Reneryo integration is healthy. The AVAROS web API reports a configured adapter, a verified live connection, a connected database, 36 runtime intents, 19 mapped KPI metrics, and complete Line-1/Line-2/Line-3 metric coverage. All 19 KPI voice paths returned spoken values during the audit.

The browser voice path was initially reported as failing, but a protocol-accurate replay now confirms that HiveMind authenticates, forwards the browser utterance to OVOS, and returns the `speak` event correctly. The earlier negative result was caused by the audit probe failing to append/decode HiveMind's separate AES-GCM `tag` field; the production browser client already handles that field. Direct messagebus and corrected browser-style queries both work.

For this server's current plain-HTTP LAN deployment, browser payload encryption is now explicitly disabled and the HiveMind client crypto key is cleared. This is required because Web Crypto is unavailable on an ordinary HTTP IP-address origin. HiveMind access-key authentication remains enabled. HTTPS deployments should re-enable payload encryption.

## Test coverage

### KPI voice coverage

All 19 configured KPI intents were queried for Line-1 and returned a value:

| KPI | Result | Example spoken response |
|---|---|---|
| energy per unit | PASS | 2.4 kilowatt hours |
| total energy | PASS | 15394.1 kilowatt hours |
| peak demand | PASS | 369.9 kilowatts |
| peak tariff exposure | PASS | 12.5 percent |
| scrap rate | PASS | 4.3 percent |
| rework rate | PASS | 3.1 percent |
| material efficiency | PASS | 89.5 percent |
| recycled content | PASS | 31.1 percent |
| supplier lead time | PASS | 7.3 days |
| supplier defect rate | PASS | 1.9 percent |
| supplier on-time rate | PASS | 88.0 percent |
| supplier CO2 per kg | PASS* | 1.6 kilograms |
| OEE | PASS | 71.9 percent |
| throughput | PASS | 115.8 units/hr |
| cycle time | PASS | 28.8 seconds |
| changeover time | PASS | 47.6 minutes |
| CO2 per unit | PASS | 1.6 kilograms |
| total CO2 | PASS | 11719.8 kilograms |
| CO2 per batch | PASS | 82.8 kilograms |

`*` The request was understood, but the response said “carbon per unit” rather than explicitly saying “supplier CO2 per kg”; see F-005.

### Natural-language and analytics coverage

- Asset aliases: `Line-1`, `Line 1`, `line one`, and `L1` all resolved successfully.
- Time windows: today, yesterday, this week, last week, last two weeks, this month, and last month returned values.
- Comparisons: exact energy, OEE, and scrap comparisons between Line-1 and Line-2 returned responses.
- Trends: energy, OEE, scrap, and generic metric trends returned direction and percentage change when a period was explicit.
- Anomalies: broad checks returned `No unusual patterns detected across 57 checks.`
- What-if: temperature and percentage-change scenarios returned calculated before/after values and assumptions.
- Controls: on/off commands safely reported that no intent binding is configured; no upstream control call was made.
- System/profile: status, active profile, asset list, greeting, help, and capabilities responded.
- Forecast/drift: both returned clear “not configured” responses because PREVENTION is disabled.

### API and integration checks

| Check | Result |
|---|---|
| `/health` | PASS, HTTP 200 |
| API without key | PASS, HTTP 401 |
| API with wrong key | PASS, HTTP 401 |
| API with `changeme` | PASS, HTTP 200 |
| live status / connection verification | PASS |
| metric catalogue | PASS, 19 metrics |
| asset mapping/linking | PASS, 3 assets with 19 metrics each |
| Reneryo asset discovery | PASS |
| production-data template/list/summary reads | PASS |
| emission-factor reads/presets | PASS |
| TTS public endpoint | PASS, valid WAV returned |
| TTS protected endpoint | PASS; unauthorized request rejected |
| focused unit/use-case suite | PASS, 153 passed |

No production records, KPI baselines, snapshots, emission factors, intent bindings, or profile settings were written during this audit.

## Findings

### F-001 — CLOSED — Audit probe incorrectly reported a browser HiveMind failure

A first audit probe authenticated through the Web UI proxy and HiveMind logged that it forwarded the utterance to the OVOS agent bus, but the probe reported no `speak` event. The probe was incomplete: HiveMind responses may contain a separate AES-GCM `tag` field, and the probe tried to decrypt only `nonce + ciphertext`.

Evidence:

```text
The energy per unit for Line 1 is 2.4 kilowatt hours
events: activate, kpi.energy.per_unit.intent, mycroft.skill.handler.start, speak
```

Conclusion: no AVAROS/HiveMind production fix is required for this finding. Keep a protocol-accurate browser-path regression test so future encryption changes do not recreate this false negative.

### F-002 — HIGH — Unknown assets silently fall back to Line-1

Query:

```text
What is the OEE for Line-99?
```

Response:

```text
The overall equipment effectiveness for Line 1 is 71.9 percent
```

This is dangerous because the answer looks valid but belongs to another asset. Unknown asset IDs should produce an explicit “asset not found” response and never fall back to the first configured asset.

### F-011 — CLOSED — LAN HTTP browser encryption configuration mismatch

The browser screenshot showed a plain HTTP page while the frontend was configured with a HiveMind crypto key. The WebSocket could connect, but browser-side Web Crypto failed before encrypted utterances were sent; the Web UI then displayed `I can't send this right now`.

Resolution applied:

```text
HIVEMIND_BROWSER_ENCRYPTION_ENABLED=false
HIVEMIND_CLIENT_CRYPTO_KEY=
```

The Web UI and HiveMind containers were recreated. The API now returns a same-origin `ws://` URL with an empty browser secret, HiveMind persisted `crypto_key=cleared`, and a browser-style plain WebSocket query returned a correct KPI response.

### F-003 — HIGH — Some comparison phrasing returns a single KPI instead of comparing

Exact “compare … between Line-1 and Line-2” forms worked. These forms did not compare:

```text
Which has lower scrap rate, Line-1 or Line-2?
→ The scrap rate for Line 1 is 4.3 percent

Which line has better OEE, Line-1 or Line-2?
→ The overall equipment effectiveness for Line 1 is 71.9 percent
```

The response should either perform the comparison or clearly ask the user to name both assets in a supported form.

### F-004 — MEDIUM — Trend responses can be incomplete or misrouted

Without an explicit period, several trend responses ended with an empty period:

```text
scrap rate is trending down, decreasing 19.6 percent over
overall equipment effectiveness is trending down, decreasing 7.5 percent over
```

Also, `How has energy been trending this month?` returned `Drift monitoring is not configured` instead of a normal trend result. Explicit forms such as `Show scrap rate trend for Line-1 last week` worked. The parser should distinguish trend requests from drift requests and always include a valid period or omit the trailing phrase.

### F-005 — MEDIUM — Supplier CO2 response label is misleading

`What is the supplier CO2 per kilogram for Line-1?` returned `The carbon per unit for Line 1 is 1.6 kilograms`. The numerical path responded, but the spoken label does not confirm that it is the supplier metric or that the unit is per kilogram. This can cause users to confuse it with CO2 per unit.

### F-006 — MEDIUM — Broad anomaly and targeted anomaly behavior is inconsistent

Broad anomaly checks use the local statistical path and returned a clear 57-check result. Targeted checks such as `Check anomalies for energy on Line-1` returned `Anomaly detection is not configured` while PREVENTION is disabled. The product should either support the documented local fallback for targeted checks or explain consistently that only broad local checks are available.

### F-007 — MEDIUM — Ambiguous utterances can time out without a recovery prompt

Examples that produced no spoken response during the live matrix:

```text
What is the number?
Tell me everything about the factory
```

An end user should receive a short clarification or capability prompt instead of silence/timeout.

### F-008 — LOW — Help text underreports the configured capability surface

The runtime exposes 36 intents and 19 KPI metrics, but the spoken help/capability responses mention only a small subset: energy per unit, OEE, scrap, energy trends, anomalies, comparisons, and temperature simulations. Add the remaining KPI families, profile/status, assets, CO2, supplier, material, and production metrics or provide a concise “say ‘list capabilities’ for the complete list” response.

### F-009 — LOW — API intent catalogue is smaller than runtime intent coverage

`/api/v1/status` reports 36 loaded runtime intents, while `/api/v1/config/intents` returns 28 catalogue entries. The missing entries are fallback/system capabilities such as greeting, help, generic trends, drift, forecast, what-if, and asset listing. This may be intentional, but the API should document the distinction or expose one complete capability catalogue.

### F-010 — TEST INFRASTRUCTURE — Isolated E2E stack is not currently runnable

The repository E2E script failed before tests because the separate `smartgic/ovos-core:latest` container crashes with:

```text
TypeError: PipelinePlugin.__init__() takes from 1 to 2 positional arguments but 3 were given
```

When tests were forced past that startup condition, HiveMind tests had no responses and direct voice tests received the mock “trouble connecting to the data source” response. The focused 153-test suite passed, but a larger service suite was not hermetic: its shared test database caused profile state to leak between tests, producing duplicate-profile setup errors. Pin the E2E OVOS image/plugin versions and isolate/reset test databases before treating the full suite as authoritative.

## Recommended fix order

1. Reject unknown assets instead of silently selecting the first asset.
2. Repair comparison routing for “which is better/lower/higher” wording.
3. Fix trend period parsing/formatting and the trend-versus-drift classifier.
4. Correct supplier CO2 response labels and add response-quality assertions for metric name and unit.
5. Make targeted anomaly fallback behavior consistent with broad anomaly checks.
6. Add clarification responses for unmatched or overly broad questions.
7. Expand/document the help capability list and reconcile the 36-versus-28 intent catalogue.
8. Pin and repair the isolated OVOS E2E environment, then make its database fixtures isolated.
9. Retain a protocol-accurate live HiveMind browser-path regression test.

## Final state

The live stack was left running after the audit. Final status remained configured and healthy, with a verified Reneryo connection and direct messagebus KPI responses working. The temporary isolated E2E containers and network were removed after testing.
