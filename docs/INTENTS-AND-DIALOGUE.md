# AVAROS Intents and Dialogue Contract

Status: verified against AVAROS commit `8258ca95f61c17af444809f84e60ba55db941156`
Verification date: 2026-08-10

## Runtime intent model

The OVOS skill registers 36 English intent files at runtime:

- 19 canonical KPI intents from `INTENT_METRIC_MAP`;
- 17 non-KPI intents from `NON_KPI_INTENT_MAP`.

Registration occurs in `AVAROSSkill._register_intent_handlers()`. KPI intent
files share `_handle_generic_kpi`; non-KPI files bind to named handlers. Dynamic
entity files for `asset`, `asset_a`, `asset_b`, and `period` are registered at
the same time.

The source directory contains 36 `.intent` files and 16 `.dialog` files under
`skill/locale/en-us/` at the verified commit.

## KPI intent map

| Intent identifier | Canonical metric | Handler operation |
|---|---|---|
| `kpi.energy.per_unit` | `energy_per_unit` | `QueryDispatcher.get_kpi` |
| `kpi.energy.total` | `energy_total` | `QueryDispatcher.get_kpi` |
| `kpi.peak_demand` | `peak_demand` | `QueryDispatcher.get_kpi` |
| `kpi.peak_tariff_exposure` | `peak_tariff_exposure` | `QueryDispatcher.get_kpi` |
| `kpi.scrap_rate` | `scrap_rate` | `QueryDispatcher.get_kpi` |
| `kpi.rework_rate` | `rework_rate` | `QueryDispatcher.get_kpi` |
| `kpi.material_efficiency` | `material_efficiency` | `QueryDispatcher.get_kpi` |
| `kpi.recycled_content` | `recycled_content` | `QueryDispatcher.get_kpi` |
| `kpi.supplier_lead_time` | `supplier_lead_time` | `QueryDispatcher.get_kpi` |
| `kpi.supplier_defect_rate` | `supplier_defect_rate` | `QueryDispatcher.get_kpi` |
| `kpi.supplier_on_time` | `supplier_on_time` | `QueryDispatcher.get_kpi` |
| `kpi.supplier_co2_per_kg` | `supplier_co2_per_kg` | `QueryDispatcher.get_kpi` |
| `kpi.oee` | `oee` | `QueryDispatcher.get_kpi` |
| `kpi.throughput` | `throughput` | `QueryDispatcher.get_kpi` |
| `kpi.cycle_time` | `cycle_time` | `QueryDispatcher.get_kpi` |
| `kpi.changeover_time` | `changeover_time` | `QueryDispatcher.get_kpi` |
| `kpi.co2.per_unit` | `co2_per_unit` | `QueryDispatcher.get_kpi` |
| `kpi.co2.total` | `co2_total` | `QueryDispatcher.get_kpi` |
| `kpi.co2.per_batch` | `co2_per_batch` | `QueryDispatcher.get_kpi` |

Before dispatching a matched KPI intent, `_handle_generic_kpi` examines the raw
utterance for anomaly, drift, forecast, what-if, trend, and comparison phrases.
If one is found, it redirects to the corresponding analytical handler. This is
an explicit guard against a broad KPI pattern winning OVOS intent resolution.

## Non-KPI intent map

| Intent file | Bound handler | Implemented behavior |
|---|---|---|
| `greeting.intent` | `handle_greeting` | Speaks `greeting.response` dialog |
| `help.intent` | `handle_help` | Speaks `help.response` dialog |
| `compare.energy.intent` | `handle_compare_energy` | Compares resolved energy metric across two assets |
| `compare.metric.intent` | `handle_compare_metric` | Resolves metric and compares two assets |
| `trend.scrap.intent` | `handle_trend_scrap` | Requests scrap-rate trend |
| `trend.energy.intent` | `handle_trend_energy` | Requests energy trend |
| `trend.metric.intent` | `handle_trend_metric` | Resolves metric and requests trend |
| `anomaly.production.check.intent` | `handle_anomaly_check` | Runs one pair or multi-pair anomaly scan depending on resolved scope |
| `drift.production.check.intent` | `handle_drift_check` | Runs PREVENTION-backed drift check |
| `forecast.metric.intent` | `handle_forecast_metric` | Runs PREVENTION-backed forecast |
| `whatif.scenario.intent` | `handle_whatif_scenario` | Builds and evaluates bounded percentage/target scenario |
| `control.device.turn_on.intent` | `handle_control_turn_on` | Requires binding on configured profiles, then sets AVAROS profile runtime power state to `on` |
| `control.device.turn_off.intent` | `handle_control_turn_off` | Requires binding on configured profiles, then sets AVAROS profile runtime power state to `off` |
| `status.system.show.intent` | `handle_status_system_show` | Speaks power/profile/platform/adapter/PREVENTION status |
| `status.profile.show.intent` | `handle_status_profile_show` | Speaks active profile and platform |
| `list.assets.intent` | `handle_list_assets` | Lists resolved asset registry |
| `help.capabilities.list.intent` | `handle_help_capabilities_list` | Speaks mapped metric capability summary plus generic operations |

### Control intent boundary

The verified control handlers do not execute the configured binding's HTTP
method or endpoint. They check only that a binding exists when a real profile is
active, then persist `runtime:power_state:{profile}` in `SettingsService` and
speak confirmation. Therefore an intent binding is configuration metadata and
a guard in this release; it is not an implemented upstream Reneryo control
call.

## Configuration catalogue versus runtime catalogue

`skill/services/settings.py::KNOWN_INTENTS` contains 28 configurable intent
identifiers. `skill/_intent_maps.py` registers 36 runtime intent files. The
following runtime intents are not present in `KNOWN_INTENTS` at the verified
commit:

- `greeting`
- `help`
- `compare.metric`
- `trend.metric`
- `drift.production.check`
- `forecast.metric`
- `whatif.scenario`
- `list.assets`

Consequently, `GET /api/v1/config/intents` is a 28-item configuration catalogue,
not a complete inventory of runtime OVOS intent files. `GET /api/v1/status`
counts `.intent` files from the locale directory and therefore reports the
runtime file count independently.

## Query operations

| Operation | Dispatcher method | Result type | External dependency |
|---|---|---|---|
| KPI | `get_kpi` | `KPIResult` | Adapter, or local derivation for selected metrics |
| Comparison | `compare` | `ComparisonResult` | Adapter |
| Trend | `get_trend` | `TrendResult` | Adapter, or carbon derivation |
| Anomaly | `check_anomaly` / `scan_anomalies` | `AnomalyResult` / `AnomalyScanResult` | Adapter series + PREVENTION client; client has local-series fallback on PREVENTION query failure |
| Drift | `check_drift` | `DriftReport` | Adapter series + PREVENTION client |
| Forecast | `forecast_metric` | `ForecastReport` | Adapter series + PREVENTION client |
| What-if | `simulate_whatif` | `WhatIfResult` | Current KPI baseline from dispatcher/adapter and deterministic scenario calculation |

The class comment in `ManufacturingAdapter` uses the historical phrase "five
query types", but the verified dispatcher exposes the operations above. Raw
data retrieval is an adapter contract used internally by analytics, not a
user-facing intent.

## Slot and entity resolution

| Entity/slot | Runtime purpose | Source |
|---|---|---|
| `asset` | Single target asset | `asset.entity`, dynamic profile asset generation, `_slot_resolution.py` |
| `asset_a`, `asset_b` | Pair used by comparisons | corresponding entity files and comparison resolver |
| `period` | Natural-language time range | `period.entity`, `TimePeriod.from_natural_language`, metric period resolver |
| `metric` | Canonical metric phrase | Intent pattern plus raw-utterance resolution in `_metric_resolver.py` |
| `amount` | What-if numeric percentage | handler numeric parsing and utterance regex |

Asset resolution uses configured IDs, display names, and aliases. Entity files
are regenerated from settings when asset configuration changes through the
implemented refresh path.

## Time-period behavior

Supported explicit phrases in the metric handler are:

- `today`, `yesterday`;
- `this week`, `last week`, `past week`;
- `last two weeks`, `last 2 weeks`;
- `this month`, `last month`, `past month`.

For an implicit period, the metric handler can use a wide range beginning
2021-02-01 UTC. Native cumulative energy-only assets can instead use their
configured aggregate-total period and reject explicit time-window queries when
the upstream mapping cannot carry period placeholders.

## Intent fallback paths

AVAROS is an `OVOS FallbackSkill` and returns `False` from `converse()`, so it
does not intercept the converse stage. In addition to registered Padatious
intent files, it provides:

1. a skill fallback that checks whether the utterance resolves to a metric or
   analytical keyword;
2. an intent-failure recovery handler for KPI, anomaly, drift, forecast, and
   what-if requests; and
3. guards in the generic KPI handler for analytical phrases.

Fallback handling returns `False` when no metric or supported analytical form
is recognized, allowing OVOS to continue to other skills.

## Dialogue and response construction

Most data-bearing replies are constructed by
`skill/services/response_builder.py`, not by static `.dialog` files.

| Result | Formatter |
|---|---|
| KPI | `ResponseBuilder.format_kpi_result` |
| Comparison | `ResponseBuilder.format_comparison_result` |
| Trend | `ResponseBuilder.format_trend_result` |
| Anomaly pair | `ResponseBuilder.format_anomaly_result` |
| Anomaly scan | `ResponseBuilder.format_anomaly_scan_result` |
| Drift | `ResponseBuilder.format_drift_result` |
| Forecast | `ResponseBuilder.format_forecast_result` |
| What-if | `ResponseBuilder.format_whatif_result` |
| Asset list | `ResponseBuilder.format_asset_list` |

`ResponseBuilder` resolves friendly asset names through the configured resolver
and formats units and values for speech. Its default verbosity is `normal`.

Static dialogue files are used directly for greeting, help, empty asset lists,
and selected error/legacy response paths. The presence of a `.dialog` file does
not by itself prove that the current handler calls it; the handler and response
builder are authoritative for the active output path.

## Failure behavior

Handlers run external/data work through `_safe_dispatch`. Domain and adapter
exceptions are converted to user-facing messages by the skill failure path.
Typical verified failures include:

- unconfigured platform;
- unknown asset;
- unsupported metric for an energy-only asset;
- missing metric mapping or per-asset resource link;
- unavailable explicit period for a cumulative-only source;
- missing production data or emission factor for derived metrics;
- PREVENTION not configured or unreachable;
- missing action intent binding on a configured profile.

## Source map

- Registration: `skill/__init__.py::_register_intent_handlers`
- Maps: `skill/_intent_maps.py`
- Utterances: `skill/locale/en-us/*.intent`
- KPI/analytics handlers: `skill/_metric_handlers.py`, `skill/_handlers.py`
- System/control handlers: `skill/_system_handlers.py`
- Metric and slot resolution: `skill/_metric_resolver.py`,
  `skill/_slot_resolution.py`, `skill/_asset_resolution.py`
- Dialogue formatting: `skill/services/response_builder.py`
- Configuration catalogue: `skill/services/settings.py::KNOWN_INTENTS`
- Tests: `tests/test_use_cases/`, `tests/test_services/`,
  `tests/test_integration/test_skill_initialization.py`
