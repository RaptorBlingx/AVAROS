---
applyTo: "**/docker/**,**/docker-compose*.yml,**/Dockerfile*"
---
# Docker & Deployment Rules

## Container Architecture
```
┌─────────────────────────────────────────────────┐
│              Docker Compose Stack               │
├─────────────┬─────────────┬─────────────────────┤
│  ovos-core  │  ovos-avaros│   docubot          │
│  (voice)    │  (skill)    │   (RAG)            │
├─────────────┴─────────────┴─────────────────────┤
│              prevention (anomaly)               │
├─────────────────────────────────────────────────┤
│              Backend Adapter (configurable)     │
└─────────────────────────────────────────────────┘
```

## Dockerfile Rules
- Use multi-stage builds for smaller images
- Pin base image versions (no `latest`)
- Non-root user for runtime
- Health checks required
- Labels for metadata (version, maintainer)

## Docker Compose Rules
- Use `.env` file for all configuration
- Named volumes for persistence
- Networks isolated per service group
- Restart policies: `unless-stopped`
- Resource limits defined

## Environment Variables
- `AVAROS_BACKEND_TYPE` - adapter selection (reneryo, mock, etc.)
- `AVAROS_BACKEND_URL` - API base URL
- `AVAROS_LOG_LEVEL` - DEBUG, INFO, WARNING, ERROR
- Secrets via Docker secrets or environment, NEVER in image

## Portability
- No hardcoded paths
- Config via environment or mounted volumes
- Works on Linux, macOS, Windows (WSL2)
