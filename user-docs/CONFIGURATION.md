# AVAROS configuration

AVAROS uses two configuration layers:

- `.env` for deployment, ports, API access, and service bootstrap credentials
- Web wizard profiles for manufacturing platform endpoints, assets, metrics, and optional analytics

## Deployment settings

Important `.env` values:

| Variable | Purpose | Recommended production value |
|---|---|---|
| `AVAROS_WEB_API_KEY` | Web UI and REST API login | Random 64-character hex value |
| `AVAROS_WEB_BIND_ADDRESS` | Host address for direct Web UI port binding | `127.0.0.1` behind a reverse proxy |
| `AVAROS_WEB_PORT` | Web UI and same-origin browser voice host port | Any available port, default `8080` |
| `TZ` | Server timezone | Site timezone |
| `HIVEMIND_WS_URL` | Browser voice WebSocket | Keep `auto`; it follows `AVAROS_WEB_PORT` |
| `HIVEMIND_MASTER_KEY` | HiveMind administration | Random secret |
| `HIVEMIND_CLIENT_KEY` | Browser voice access key | Random secret |
| `HIVEMIND_CLIENT_SECRET` | HiveMind client password | Random secret |
| `HIVEMIND_CLIENT_CRYPTO_KEY` | Voice payload encryption key | 16, 24, or 32 characters |
| `PREVENTION_URL` | Optional PREVENTION endpoint | Empty when unused |
| `PREVENTION_EXPORT_ENABLED` | Continuous analytics data export | `false` when PREVENTION is unused |
| `AVAROS_SERVER_TTS_ENABLED` | Server-backed response audio for browser playback | `true` for demos, disable if not needed |

Run `bash scripts/prepare-env.sh` to generate the required secrets.

After changing `.env`:

```bash
docker compose up -d --force-recreate
```

Changing `AVAROS_WEB_PORT` does not require changing HiveMind settings. With
`AVAROS_WEB_PORT=9090`, the browser receives
`ws://localhost:9090/hivemind/`, while the Web UI reaches HiveMind internally
at `hivemind:5678`.

## Platform wizard

Create one profile per platform or site.

### Platform connection

Enter the API base URL reachable from the AVAROS containers. Do not use `localhost` for another container or a remote service.

Supported authentication patterns include:

- no authentication
- bearer/API token
- session cookie
- configurable headers supported by the generic REST profile

Use **Test connection** before saving.

### Assets and resources

Register the names operators will say, such as `Line-1`, `Press-2`, or `Supplier-A`. Add aliases for natural speech.

Link each AVAROS asset to the corresponding platform resource identifier.

### Metric mapping

Map platform responses to AVAROS canonical metrics. AVAROS supports 19 metrics:

- Energy: energy per unit, total energy, peak demand, peak tariff exposure
- Production: OEE, throughput, cycle time, changeover time
- Material: scrap rate, rework rate, material efficiency, recycled content
- Carbon: CO2 per unit, total CO2, CO2 per batch
- Supplier: lead time, defect rate, on-time delivery, CO2 per kilogram

Test each mapping with the wizard before enabling its intent.

### Intent activation

Enable only commands backed by valid data. This prevents operators from receiving responses for unconfigured metrics.

## Production CSV data

The Production Data page accepts:

```text
date,asset_id,production_count,good_count,material_consumed_kg,shift,batch_id,notes
```

See `examples/sample-production-data.csv`.

## PREVENTION

PREVENTION can be configured in the wizard or through environment variables. Environment values take precedence when set.

Supported modes:

- `none`
- `bearer`
- `keycloak_client_credentials`

Leave PREVENTION disabled if the endpoint, data contract, or authorization details have not been provided.

## API use

All protected API requests require:

```http
X-API-Key: <AVAROS_WEB_API_KEY>
```

Example:

```bash
curl http://localhost:8080/api/v1/status \
  -H "X-API-Key: ${AVAROS_WEB_API_KEY}"
```
