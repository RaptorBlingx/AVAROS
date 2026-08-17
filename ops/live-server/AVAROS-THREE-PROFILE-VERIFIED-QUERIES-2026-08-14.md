# AVAROS three-profile manual verification checklist

Date: 2026-08-14
Profiles: `reneryo`, `thingsboard-ce`, `openems`
Scope: end-user voice/text queries through the AVAROS Web UI. Device-control commands are intentionally out of scope.

## How to run the check

1. Open [AVAROS Web UI](https://avaros.reneryo.com/).
2. Open **Settings**, select one profile, click **Switch**, and confirm that it shows **Active**.
3. Ask `Which profile is active?` before testing that profile.
4. Ask each query below one at a time. Tick the result only after the spoken/text response matches the expected behavior.
5. Switch to the next profile and repeat. Do not assume that a response from one profile proves another profile works.

For numeric answers, record the value and unit in the Notes column. Live values can change; the response shape, unit, asset name, and profile are the important checks.

## 1. RENERYO (`reneryo`)

Use `Line-1` and `Line-2` for line KPIs and comparisons. Use `Electric Main Meter` for the direct meter-energy check.

| Done | End-user query | Verified/expected result | Notes |
|---|---|---|---|
| [ ] | `Which profile is active?` | Reports `reneryo` on `custom_rest`. | |
| [ ] | `Show system status` | Reports the system online, active profile, adapter, and live status. | |
| [ ] | `List capabilities` | Lists the capabilities currently mapped and enabled for RENERYO. | |
| [ ] | `List assets` | Lists the configured RENERYO assets. | |
| [ ] | `What is the total energy of Electric Main Meter?` | Returns a numeric total-energy value with an energy unit. | |
| [ ] | `What is the energy per unit for Line 1 last week?` | Returns a numeric KPI value with the energy-per-unit unit. | |
| [ ] | `What is the total energy for Line 1 last week?` | Returns a numeric total-energy KPI. | |
| [ ] | `What is the OEE for Line 1 last week?` | Returns a numeric OEE value (normally expressed as a percentage). | |
| [ ] | `Compare energy between Line 1 and Line 2 last week` | Returns a comparison (higher/lower, difference, or equivalent comparison wording). | |
| [ ] | `Show energy trend for Line 1 last week` | Returns a trend summary. | |
| [ ] | `Show OEE trend for Line 1 last week` | Returns a trend summary, if the mapped OEE history is available. | |
| [ ] | `Check production anomaly for Line 1` | Returns an anomaly/normality summary; prevention analysis can take several seconds. | |
| [ ] | `Check anomalies for energy on Line 1` | Returns an energy-anomaly status. | |
| [ ] | `Check for drift in energy on Line 1` | Returns a drift/trend summary. | |
| [ ] | `Forecast energy for Line 1` | Returns a forecast summary when the forecast data is available. | |
| [ ] | `What if energy per unit drops by 5 percent for Line 1` | Returns a decision-support scenario, not a device command. | |

RENERYO caveat: energy-only meter assets (for example, Gas Main Meter, Meter-1, and Water Main Meter) are appropriate for direct total-energy questions only; do not use them to validate line trends.

## 2. ThingsBoard CE (`thingsboard-ce`)

The verified native telemetry check uses `Test Device A1`. The ThingsBoard trend currently has one native point in the selected period, so a **stable** result is expected; this validates the endpoint and parser, not a rich time series.

| Done | End-user query | Verified/expected result | Notes |
|---|---|---|---|
| [ ] | `Which profile is active?` | Reports `thingsboard-ce` on `custom_rest`. | |
| [ ] | `Show system status` | Reports the system online, active profile, adapter, and live status. | |
| [ ] | `List capabilities` | Lists the ThingsBoard metrics that are mapped and enabled. | |
| [ ] | `List assets` | Lists the configured ThingsBoard devices/assets. | |
| [ ] | `What is the energy per unit for Test Device A1?` | Returns a numeric value in `kWh/unit` (the verified run returned about `1.2 kWh/unit`; live data may change). | |
| [ ] | `Show energy trend for Test Device A1 today` | Returns a trend summary; with the current native point, `stable` is expected. | |
| [ ] | `What is the total energy for Test Device A1?` | Returns a numeric total-energy value if that metric is enabled in the selected profile. | |
| [ ] | `What is the OEE for Test Device A1?` | Returns a numeric OEE value if that metric is enabled; otherwise it should clearly say it is not configured/unavailable. | |
| [ ] | `Compare energy between Test Device A1 and Test Device A2` | Returns a comparison when both device values are available. | |
| [ ] | `Are there any unusual patterns today?` | Returns an anomaly/normality summary when the mapped data supports it. | |

ThingsBoard caveats:

- A device with no native telemetry should produce a clear unavailable/no-data response, not a fabricated value.
- Device control is not part of this checklist.
- ThingsBoard CE can be opened directly at `http://10.33.10.112:8180` when that host port is reachable. The demo tenant credentials previously used were `tenant@thingsboard.org` / `tenant`.

## 3. OpenEMS (`openems`)

OpenEMS is configured as a live energy-system profile. The following nine metric queries are direct mappings to native OpenEMS Edge REST channels; no AVAROS-generated telemetry is used.

| Done | End-user query | Verified/expected result | Notes |
|---|---|---|---|
| [ ] | `What is total energy for OpenEMS Edge?` | Native `_sum/ConsumptionActiveEnergy`; numeric `Wh`, increasing while the simulator runs. | |
| [ ] | `How much power is OpenEMS Edge consuming?` | Native `_sum/ConsumptionActivePower`; numeric `W`. | |
| [ ] | `How much power is OpenEMS Edge producing?` | Native `_sum/ProductionActivePower`; numeric `W`. | |
| [ ] | `What is produced energy for OpenEMS Edge?` | Native `_sum/ProductionActiveEnergy`; numeric `Wh`, increasing while the simulator runs. | |
| [ ] | `What is grid power for OpenEMS Edge?` | Native `_sum/GridActivePower`; numeric `W` (positive = buying, negative = feeding in). | |
| [ ] | `What is energy imported from grid?` | Native `_sum/GridBuyActiveEnergy`; numeric `Wh`. | |
| [ ] | `What is energy exported to grid?` | Native `_sum/GridSellActiveEnergy`; numeric `Wh`. | |
| [ ] | `What is battery state of charge for OpenEMS Edge?` | Native `_sum/EssSoc`; numeric percentage. | |
| [ ] | `What is battery power for OpenEMS Edge?` | Native `_sum/EssActivePower`; numeric `W` (negative = charging, positive = discharging). | |
| [ ] | `List capabilities` | Lists the nine mapped OpenEMS metrics, plus the enabled profile/status capabilities. | |
| [ ] | `Which profile is active?` | Reports `openems` on `custom_rest`. | |
| [ ] | `Show system status` | Reports the system online, active profile, adapter, and `GenericRestAdapter`. | |
| [ ] | `List assets` | Lists one configured asset: `OpenEMS Edge`. | |

The OpenEMS simulator natively supplies these live Edge channels. A historical trend is not enabled yet because the current Edge-only deployment has no native timedata service/database. AVAROS will not synthesize a history merely to make a trend query answer; an OpenEMS Backend plus its Timedata/InfluxDB service is the native next step for historical trends.

## Cross-profile isolation checks

Run these after switching profiles:

| Check | Pass condition |
|---|---|
| Active-profile query | The response names the profile just selected. |
| Asset list | Assets belong to the selected platform; no Reneryo, ThingsBoard, or OpenEMS asset leaks into another profile. |
| Metric query | A supported metric returns that profile's value/unit; an unmapped metric says unavailable/not configured. |
| OpenEMS live-energy queries | Each of the nine OpenEMS metric questions returns a value with the expected unit and does not use another profile's endpoint. |
| Authentication/data source | No “authentication failed”, connection error, or cross-platform endpoint error appears. |

## Interpreting an unexpected response

- **No data / not configured** for an intentionally unmapped metric is an expected result, not an adapter failure.
- **Disabled for the active profile** is expected for an OpenEMS historical trend until native OpenEMS timedata is deployed.
- A response containing another profile name or another profile's asset is a profile-isolation defect.
- A timeout, authentication error, fabricated number, wrong unit, or missing asset is a defect to capture in the Notes column with the exact query and timestamp.

## OpenEMS access details

The official OpenEMS Edge UI is deployed and reachable from your browser:

- OpenEMS UI: `http://10.33.10.112:8186`
  - Use the default guest login by leaving the password empty.
  - Enter `admin` as the password for extended local demo permissions.

The UI proxies to the running OpenEMS Edge websocket and displays the same native simulator data used by AVAROS. The remaining management/API ports are local to the server:

- Web Console (Apache Felix): `http://127.0.0.1:8182/system/console`
  - Login: `admin`
  - Password: `admin`
- REST API base: `http://127.0.0.1:8184/rest`
  - HTTP Basic demo credential: username `x`, password `admin` (`x:admin`)
- Port `8185` is the OpenEMS websocket endpoint, not a browser HTTP UI.

The `127.0.0.1` management/API URLs work on the AVAROS server itself. The browser UI is intentionally exposed at `http://10.33.10.112:8186`. The official OpenEMS Docker guide documents the Edge UI deployment, and the [OpenEMS timedata guide](https://openems.github.io/openems.io/openems/latest/backend/timedata.html) describes the native history path required for trends.
