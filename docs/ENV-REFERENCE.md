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

## Platform Adapter

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `ADAPTER_TYPE` | No | `mock` | Skill | Platform adapter to use: `mock` (demo data) or `reneryo` (production) |

> **Note:** Platform credentials (API URL, authentication) are entered via the Web UI wizard and stored encrypted in the database — not in environment variables.

## Web UI

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `AVAROS_WEB_UI_PORT` | No | `8080` | Web UI | Internal port for the FastAPI web server |
| `AVAROS_WEB_API_KEY` | Recommended | *(auto-generated)* | Web UI | API key for authenticating Web UI and API requests. If not set, a random key is generated on startup and logged. **Set explicitly for production.** |

## HTTPS / TLS (Nginx Proxy)

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `AVAROS_HTTPS_PORT` | No | `443` | Proxy | External HTTPS port mapped to the host |
| `AVAROS_HTTP_PORT` | No | `80` | Proxy | External HTTP port (redirects to HTTPS) |
| `AVAROS_TLS_MODE` | No | `self-signed` | Proxy | TLS mode: `self-signed` or `letsencrypt` |

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

These variables configure the `tools/reneryo-mock/generator.py` daemon that seeds and continuously writes manufacturing data into Reneryo for all 19 AVAROS canonical metrics.

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

For a standard Docker deployment, only two variables typically need customization:

```bash
# 1. Set adapter to production
ADAPTER_TYPE=reneryo

# 2. Set a secure API key
AVAROS_WEB_API_KEY=your-secure-32-char-hex-key-here
```

All other variables have sensible defaults for Docker Compose deployment.
