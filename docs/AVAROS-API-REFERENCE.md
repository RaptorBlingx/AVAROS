# AVAROS API Reference

Status: verified against AVAROS commit `8258ca95f61c17af444809f84e60ba55db941156`
Verification date: 2026-08-10
Implementation: `web-ui/main.py`, `web-ui/routers/`, `web-ui/schemas/`

## Scope

This reference covers interfaces exposed by the AVAROS FastAPI service. It is
not the upstream Reneryo API reference; see `RENERYO-API-REFERENCE.md` for that
contract.

AVAROS currently has **no REST endpoint for submitting a natural-language
question**. Text and voice questions enter through HiveMind WebSocket and OVOS.

## Base URL and generated schema

In the default standalone deployment, the service is available at
`http://localhost:${AVAROS_WEB_PORT:-8080}` and is bound to host loopback by
Compose. A proxy deployment may expose a different public origin.

FastAPI exposes the generated interface metadata at:

- `GET /openapi.json`
- `GET /docs`
- `GET /redoc`

The generated schema is derived directly from the route decorators and
Pydantic models named in this document.

## Authentication

FastAPI middleware requires this header for every path beginning `/api/v1/`:

```http
X-API-Key: <AVAROS_WEB_API_KEY>
```

Missing or incorrect keys return:

```json
{"detail":"Invalid or missing API key"}
```

with status `401`.

The middleware condition does not protect `/health`, documentation/schema
paths, SPA assets, `/hivemind/`, `/wakeword/*`, `/voice/preferences`, or
`/voice/tts`. HiveMind has a separate authorization requirement documented
below. The public TTS and preference routes exist for trusted embeds.

## Route catalogue

### Health and status

| Method | Path | Request | Response | Behavior |
|---|---|---|---|---|
| GET | `/health` | none | `{"status":"ok","version":"..."}` | Public liveness endpoint |
| GET | `/api/v1/status` | none | `SystemStatusResponse` | Active adapter/profile, DB, live upstream connectivity, intent count, PREVENTION runtime/capability/data status |

Live platform and PREVENTION status probes are cached for 20 seconds by the
status router.

### Platform configuration

| Method | Path | Request | Response | Behavior |
|---|---|---|---|---|
| POST | `/api/v1/config/platform` | `PlatformConfigRequest` | `PlatformConfigResponse` | Saves active platform config, attempts adapter reload, sends best-effort skill reload event |
| GET | `/api/v1/config/platform` | none | `PlatformConfigResponse` | Returns current config with masked API key |
| DELETE | `/api/v1/config/platform` | none | `ResetResponse` | Deletes active custom profile when applicable and returns to `unconfigured` |
| POST | `/api/v1/config/platform/test` | `PlatformConfigRequest` | `ConnectionTestResponse` | Tests a temporary adapter without saving configuration |

`PlatformConfigRequest` fields are `platform_type`, `api_url`, `api_key`, and
`extra_settings`. The public platform type values are `custom_rest` and
`unconfigured`; connection testing constructs only `custom_rest`.

### Named profiles

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/config/profiles` | none | `ProfileListResponse` |
| GET | `/api/v1/config/profiles/{name}` | none | `ProfileDetailResponse` |
| POST | `/api/v1/config/profiles` | `CreateProfileRequest` | `ProfileDetailResponse` (`201`) |
| PUT | `/api/v1/config/profiles/{name}` | `UpdateProfileRequest` | `ProfileDetailResponse` |
| DELETE | `/api/v1/config/profiles/{name}` | none | `DeleteProfileResponse` |
| POST | `/api/v1/config/profiles/{name}/activate` | none | `ActivateProfileResponse` |

Profile detail responses mask the upstream API key. The built-in
`unconfigured` profile cannot be created or deleted. Activation validates the
profile before changing state, reloads the adapter, rolls back on adapter
creation failure, and reports voice-bus notification success through
`voice_reloaded`.

### Assets and resource linking

| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| GET | `/api/v1/assets/mappings` | none | `AssetMappingsResponse` | Legacy read alias |
| PUT | `/api/v1/assets/mappings` | `AssetMappingsRequest` | `AssetMappingsResponse` | Legacy write alias |
| GET | `/api/v1/config/assets` | none | `AssetMappingsResponse` | Wizard/settings read |
| POST | `/api/v1/config/assets` | `AssetMappingsRequest` | `AssetMappingsResponse` | Replaces/persists active-profile asset mappings |
| GET | `/api/v1/assets/discover` | none | `AssetDiscoveryResponse` | Uses adapter discovery where supported; upstream failures return `502` |
| GET | `/api/v1/assets/linking-summary` | none | `AssetLinkingSummaryResponse` | Returns discovery, registration, linking modes, and canonical metric coverage |
| GET | `/api/v1/assets/generator-mapping-preview` | none | `GeneratorAssetPreviewResponse` | Reads bundled generator mapping without persistence |
| POST | `/api/v1/assets/import-generator-mapping` | `GeneratorMappingRequest` | `GeneratorMappingResponse` | Merges supplied metric/asset/resource mapping |
| POST | `/api/v1/assets/import-generator-mapping/default` | none | `GeneratorMappingResponse` | Imports configured/bundled `mapping_output.json` |

`AssetMappingsRequest.asset_mappings` has the transport shape
`{asset_id: mapping_object}`. Asset mapping objects can include display data,
aliases, metadata, `metric_resources`, native metric bindings, and capability
mode as interpreted by `SettingsService` and `GenericRestAdapter`.

Generator import accepts:

```json
{
  "mapping": {
    "energy_per_unit": {
      "Line-1": "reneryo-resource-uuid"
    }
  }
}
```

and merges it into per-asset `metric_resources` without discarding existing
asset display fields.

### Metric mappings

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/v1/config/metrics` | `MetricMappingRequest` | `MetricMappingResponse` (`201`) |
| GET | `/api/v1/config/metrics` | none | array-root `MetricMappingListResponse` |
| PUT | `/api/v1/config/metrics/{metric_name}` | `MetricMappingRequest` | `MetricMappingResponse` |
| DELETE | `/api/v1/config/metrics/{metric_name}` | none | empty (`204`) |
| POST | `/api/v1/config/metrics/test` | `MetricMappingTestRequest` | `MetricMappingTestResponse` |

`MetricMappingRequest` contains:

| Field | Type | Meaning |
|---|---|---|
| `canonical_metric` | one of the 19 canonical metric strings | Stable AVAROS metric name |
| `endpoint` | string | Upstream path/template |
| `json_path` | string | Value extraction path |
| `unit` | string | Unit assigned to the canonical result |
| `transform` | string or null | Optional supported value transform |

The test endpoint accepts `base_url`, `endpoint`, `json_path`, `auth_type`, and
`auth_token`; an empty or masked token is resolved from the active platform
configuration.

### Intent activation

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/config/intents` | none | `IntentListResponse` |
| PUT | `/api/v1/config/intents/{intent_name}` | `IntentToggleRequest` | `IntentStateResponse` |

The response reports `intent_name`, `active`, `required_metrics`,
`metrics_mapped`, and category (`kpi`, `action`, or `system`). This configuration
catalogue contains the `KNOWN_INTENTS` defined in `skill/services/settings.py`;
the OVOS registration catalogue is separately defined by
`skill/_intent_maps.py`. See `INTENTS-AND-DIALOGUE.md` for the verified
distinction.

### Non-metric intent bindings

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/v1/config/intent-bindings` | `IntentBindingRequest` | `IntentBindingResponse` (`201`) |
| GET | `/api/v1/config/intent-bindings` | none | array-root `IntentBindingListResponse` |
| PUT | `/api/v1/config/intent-bindings/{intent_name}` | `IntentBindingRequest` | `IntentBindingResponse` |
| DELETE | `/api/v1/config/intent-bindings/{intent_name}` | none | empty (`204`) |

The accepted binding fields are `intent_name`, `endpoint`, HTTP `method`,
`json_path`, optional `success_path`, and optional `transform`. The currently
accepted binding names are defined by
`web-ui/schemas/intent_bindings.py::NON_METRIC_INTENT_VALUES`.

### PREVENTION configuration

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/config/prevention` | none | `PreventionConfigResponse` |
| POST | `/api/v1/config/prevention` | `PreventionConfigRequest` | `PreventionConfigResponse` |
| POST | `/api/v1/config/prevention/test` | `PreventionTestRequest` | `PreventionTestResponse` |

Implemented auth modes are `none`, `bearer`, and
`keycloak_client_credentials`. Secret values are encrypted when stored through
`SettingsService` and are returned only as configured flags and masked suffixes.
Environment configuration can override stored PREVENTION endpoint/auth values;
the response reports the effective source.

### Alert configuration

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/config/alert-config` | none | `AlertConfigSchema` |
| PUT | `/api/v1/config/alert-config` | `AlertConfigSchema` | `AlertConfigSchema` |

The schema contains `enabled`, `interval_seconds`, `severity_threshold`,
`cooldown_minutes`, `monitored_pairs`, `z_score_threshold`, and the independent
`query_z_score_threshold`. These endpoints configure monitoring; they do not
return generated alert events.

### Emission factors

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/config/emission-factors` | none | `EmissionFactorListResponse` |
| POST | `/api/v1/config/emission-factors` | `EmissionFactorRequest` | `EmissionFactorResponse` |
| DELETE | `/api/v1/config/emission-factors/{energy_source}` | none | deletion status object |
| GET | `/api/v1/config/emission-factors/presets` | none | array of `EmissionFactorPresetResponse` |

An emission-factor request contains `energy_source`, numeric `factor`,
`country`, `source`, and `year`.

### Supplementary production data

Base path: `/api/v1/production-data`.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/production-data/template` | none | CSV download |
| POST | `/api/v1/production-data` | `ProductionRecordRequest` | `ProductionRecordResponse` (`201`) |
| DELETE | `/api/v1/production-data/{record_id}` | none | deletion status object |
| POST | `/api/v1/production-data/bulk` | multipart field `file` | `CsvUploadResponse` |
| GET | `/api/v1/production-data` | optional `asset_id`, `start_date`, `end_date` | `ProductionRecordListResponse` |
| GET | `/api/v1/production-data/summary` | required `asset_id`, `start_date`, `end_date` | `ProductionSummaryResponse` |

Record input fields are `record_date`, `asset_id`, `production_count`,
`good_count`, `material_consumed_kg`, `shift`, `batch_id`, and `notes`.

### KPI baselines, snapshots, and progress

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/v1/kpi/baseline` | `BaselineRequest` | `BaselineResponse` (`201`) |
| GET | `/api/v1/kpi/baseline/{site_id}` | none | array of `BaselineResponse` |
| DELETE | `/api/v1/kpi/baseline/{site_id}/{metric}` | none | deletion status object |
| POST | `/api/v1/kpi/snapshot` | `SnapshotRequest` | `SnapshotResponse` (`201`) |
| GET | `/api/v1/kpi/snapshots/{site_id}/{metric}` | optional `start_date`, `end_date` | array of `SnapshotResponse` |
| GET | `/api/v1/kpi/progress/{site_id}` | none | `SiteProgressResponse` |
| GET | `/api/v1/kpi/progress/{site_id}/{metric}` | required `current_value`, `current_unit` | `KPIProgressResponse` |
| GET | `/api/v1/kpi/export/{site_id}` | none | array of anonymized dataset objects |

The FastAPI startup event also starts `KPIScheduler`, which bootstraps and then
collects configured KPI snapshots. Its default interval is 0.25 hours and can
be overridden by `KPI_COLLECTION_INTERVAL_HOURS`.

### Voice support

Protected routes:

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/v1/voice/config` | none | `VoiceConfigResponse` |
| GET | `/api/v1/voice/preferences` | none | `VoicePreferencesResponse` |
| PUT | `/api/v1/voice/preferences` | `VoicePreferencesRequest` | `VoicePreferencesResponse` |
| POST | `/api/v1/voice/tts` | `SpeechRequest` | `audio/wav` |

Trusted-embed public routes:

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/voice/preferences` | none | JSON voice preference |
| POST | `/voice/tts` | JSON `SpeechRequest` or `text/plain` | length-limited `audio/wav` |
| OPTIONS | `/voice/preferences` | none | CORS preflight |
| OPTIONS | `/voice/tts` | none | CORS preflight |

The public routes are intentionally outside `/api/v1/`; deployment of the
widget follows the trusted-host model in `EMBEDDABLE_WIDGET.md`.

### WebSocket and proxy routes

| Protocol | Path | Authentication | Behavior |
|---|---|---|---|
| WEBSOCKET | `/hivemind/` | required `authorization` query parameter | Same-origin bidirectional proxy; forwards authorization as `X-HiveMind-Auth` |
| GET | `/wakeword/health` | none at FastAPI middleware | Proxies wake-word backend health; backend errors return `503` |
| WEBSOCKET | `/wakeword/ws/detect` | none at FastAPI middleware | Proxies binary/text frames to wake-word detector |

The HiveMind proxy accepts the browser socket before validation; absent
authorization causes close code `1008`. Backend connection failures use close
code `1011`.

## Interfaces that do not exist

No route in the verified source implements any of the following:

- `POST /ask`, `/query`, or `/chat` natural-language request;
- alert-event listing or acknowledgement;
- outbound webhook registration;
- Server-Sent Events notification stream;
- Reneryo-specific notification callback;
- public short-lived widget-session-token issuance.

These absences are relevant integration boundaries. They must not be inferred
from the presence of the configuration API or embeddable widget.

## Source map

- API assembly and middleware: `web-ui/main.py`
- Routes: `web-ui/routers/*.py`
- Shared request/response models: `web-ui/schemas/*.py`
- Asset transport models: top of `web-ui/routers/assets.py`
- Speech request model: `web-ui/routers/voice.py`
- Auth configuration: `web-ui/config.py`, `.env.example`
- Route tests: `tests/test_web_ui/`
