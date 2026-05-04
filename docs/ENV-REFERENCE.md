# AVAROS Environment Variable Reference

All environment variables used by AVAROS services. Set these in the `.env` file (copy from `.env.example`).

---

## General Settings

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `AVAROS_LOG_LEVEL` | No | `INFO` | Skill | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_LEVEL` | No | `INFO` | Skill | Alternative log level variable (same effect as `AVAROS_LOG_LEVEL`) |
| `TZ` | No | `UTC` | All | Timezone for timestamps |

## Database

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `AVAROS_DATABASE_URL` | Yes | *(none)* | Web UI, Skill | PostgreSQL connection URL. Format: `postgresql://user:pass@host:port/dbname` |
| `POSTGRES_USER` | No | `avaros` | Database | PostgreSQL user (set in Docker Compose) |
| `POSTGRES_PASSWORD` | No | `avaros` | Database | PostgreSQL password (set in Docker Compose) |
| `POSTGRES_DB` | No | `avaros` | Database | PostgreSQL database name (set in Docker Compose) |

> **Default for Docker:** `postgresql://avaros:avaros@avaros_db:5432/avaros` — works with the default Docker Compose setup.

## Platform Configuration

Platform connection is configured from the Web UI wizard and stored per profile in the database.

- No adapter selection environment variable is required.
- Runtime uses the unified REST adapter with the active profile configuration.
- API URL, auth type, and credentials are profile-scoped and not read from env vars.

## Web UI

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `AVAROS_WEB_UI_PORT` | No | `8080` | Web UI | Internal port for the FastAPI web server |
| `AVAROS_WEB_API_KEY` | Recommended | *(auto-generated)* | Web UI | API key for authenticating Web UI and API requests. If not set, a random key is generated on startup and logged. **Set explicitly for production.** |

## PREVENTION Analytics

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `PREVENTION_URL` | No | *(empty)* | Skill, Web UI | Base URL of the PREVENTION GraphQL endpoint. Leave empty when no PREVENTION runtime is available. Use `http://prevention:8081` when PREVENTION runs on the same Docker network. |
| `PREVENTION_AUTH_MODE` | No | `none` | Skill, Web UI | PREVENTION authentication mode: `none`, `bearer`, or `keycloak_client_credentials`. |
| `PREVENTION_AUTH_TOKEN` | No | *(empty)* | Skill, Web UI | Optional pre-issued bearer token for authenticated PREVENTION deployments when `PREVENTION_AUTH_MODE=bearer`. |
| `PREVENTION_KEYCLOAK_TOKEN_URL` | No | *(empty)* | Skill, Web UI | Optional Keycloak/OIDC token endpoint for PREVENTION client-credentials authentication. |
| `PREVENTION_KEYCLOAK_CLIENT_ID` | No | *(empty)* | Skill, Web UI | Optional Keycloak/OIDC client ID supplied by the PREVENTION/platform administrator. |
| `PREVENTION_KEYCLOAK_CLIENT_SECRET` | No | *(empty)* | Skill, Web UI | Optional Keycloak/OIDC client secret supplied by the PREVENTION/platform administrator. |
| `PREVENTION_KEYCLOAK_SCOPE` | No | *(empty)* | Skill, Web UI | Optional OAuth scope for PREVENTION token requests, for example `openid`. |
| `PREVENTION_DATA_MAX_AGE_MINUTES` | No | `1440` | Skill, Web UI | Maximum age of the PREVENTION export manifest before AVAROS marks analytics input data as stale. |
| `PREVENTION_EXPORT_ENABLED` | No | `true` | Exporter | Enables the continuous AVAROS profile to PREVENTION data export service. Set to `false` when PREVENTION is not used or exports are scheduled externally. |
| `PREVENTION_EXPORT_INTERVAL_SECONDS` | No | `900` | Exporter | Seconds between automatic export cycles. |
| `PREVENTION_EXPORT_DAYS` | No | `30` | Exporter | Historical lookback window exported into PREVENTION input files. |
| `PREVENTION_EXPORT_PROFILE` | No | *(active profile)* | Exporter | Optional AVAROS profile name to export. Empty means use the currently active profile. |
| `PREVENTION_PORT` | No | `8082` | PREVENTION Compose | Host port published by `docker/docker-compose.prevention.yml`. |
| `PREVENTION_MONGO_USER` | No | `prevention` | PREVENTION Compose | MongoDB username for the PREVENTION development stack. |
| `PREVENTION_MONGO_PASS` | No | `prevention` | PREVENTION Compose | MongoDB password for the PREVENTION development stack. |
| `PREVENTION_BUILD_CONTEXT` | No | `../../prevention_upd` | PREVENTION Compose | Filesystem path to the external PREVENTION repo used for local image builds. |

## HTTPS / TLS (Nginx Proxy)

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `AVAROS_HTTPS_PORT` | No | `443` | Proxy | External HTTPS port mapped to the host |
| `AVAROS_HTTP_PORT` | No | `80` | Proxy | External HTTP port (redirects to HTTPS) |
| `AVAROS_TLS_MODE` | No | `self-signed` | Proxy | TLS mode: `self-signed` or `letsencrypt` |

## HiveMind Voice Bridge

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `HIVEMIND_PORT` | No | `5678` | HiveMind | External port for the HiveMind WebSocket listener. |
| `HIVEMIND_MASTER_KEY` | Recommended | *(auto-generated)* | HiveMind | Administrative/master key for HiveMind-core. Set explicitly outside local-only demos. |
| `HIVEMIND_CLIENT_NAME` | No | `avaros-web-client` | HiveMind, Web UI | Browser client identity used in the websocket authorization token. |
| `HIVEMIND_CLIENT_KEY` | Recommended | *(auto-generated)* | HiveMind, Web UI | Browser client access key embedded in the websocket authorization token. |
| `HIVEMIND_CLIENT_SECRET` | Recommended | *(auto-generated)* | HiveMind | Browser client password stored in the HiveMind client database. |
| `HIVEMIND_CLIENT_CRYPTO_KEY` | Recommended | *(derived from secret if empty)* | HiveMind, Web UI | Shared AES key for encrypted HiveMind websocket payloads. This must match in both containers or the browser will reconnect in a loop with MAC/decryption errors. |
| `HIVEMIND_WS_URL` | No | `auto` | Web UI | Public websocket URL returned to browser clients for HiveMind connections. `auto` derives `ws(s)://<current-host>/hivemind/` from the request and is recommended behind the AVAROS proxy. |
| `HIVEMIND_CLIENT_ALLOWED_TYPES` | No | built-in allowlist | HiveMind | Comma-separated OVOS message types allowed for the browser client. |
| `WAKEWORD_BACKEND_URL` | No | `http://avaros-wakeword:9999` | Web UI | Internal wake-word backend URL used by the Web UI same-origin `/wakeword/*` proxy. Keep the Docker default unless the wake-word service is deployed separately. |

## Mock RENERYO Server

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `MOCK_RENERYO_PORT` | No | `8090` | Mock Server | Port for the mock RENERYO HTTP server (testing/demo only) |

## OVOS Configuration

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `OVOS_CONFIG_BASE_FOLDER` | No | `mycroft` | Skill | OVOS config directory name |
| `OVOS_CONFIG_FILENAME` | No | `mycroft.conf` | Skill | OVOS config file name |

## Python Runtime

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `PYTHONUNBUFFERED` | No | `1` | All | Disable Python output buffering (set in Docker Compose) |
| `PYTHONDONTWRITEBYTECODE` | No | `1` | All | Prevent `.pyc` file creation (set in Docker Compose) |

## Development Only

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `AVAROS_DEBUG` | No | `false` | Skill | Enable debug mode with verbose logging |
| `AVAROS_SKIP_AUTH` | No | `false` | Web UI | Skip API key authentication (**never use in production**) |
| `AVAROS_DATA_PATH` | No | `/data` | Skill | Path for local data storage |
| `AVAROS_PORT` | No | `8080` | Skill | Port for standalone skill API (non-Docker) |

## Reneryo Data Generator

These variables configure the `tools/reneryo-data-generator/generator.py` daemon that seeds and continuously writes manufacturing data into Reneryo for all 19 AVAROS canonical metrics.

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `RENERYO_API_URL` | No | `http://deploys.int.arti.ac:31290/api` | Generator | Reneryo API base URL |
| `RENERYO_SESSION_COOKIE` | Yes | *(none)* | Generator | Valid session cookie for Reneryo authentication. Obtain from browser DevTools after login. |
| `GENERATOR_MODE` | No | `seed` | Generator | Operating mode: `seed` (historical backfill), `daemon` (continuous every interval), `verify` (read-back check), `list` (show mapping) |
| `GENERATOR_INTERVAL` | No | `900` | Generator | Seconds between daemon writes (default 15 min) |
| `GENERATOR_SEED_DAYS` | No | `90` | Generator | Days of historical data to seed on first run |
| `GENERATOR_BATCH_DELAY` | No | `100` | Generator | Milliseconds between API batches (rate limiting) |

---

## Quick Setup

For a standard Docker deployment, two values usually need customization:

```bash
# Set a secure API key
AVAROS_WEB_API_KEY=your-secure-32-char-hex-key-here

# Enable PREVENTION only when the analytics stack is running
PREVENTION_URL=http://prevention:8081
PREVENTION_EXPORT_ENABLED=true
```

All other variables have sensible defaults for Docker Compose deployment.
