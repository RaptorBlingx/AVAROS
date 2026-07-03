# AVAROS

AVAROS is a Dockerized OpenVoiceOS (OVOS) Digital Intelligent Assistant for manufacturing teams. It provides conversational access to energy, production, material, carbon, and supplier KPIs, with optional PREVENTION-based anomaly and drift analytics.

Version: **0.1.1**
License: **Apache-2.0**

## What is included

- AVAROS OVOS skill and 19 canonical manufacturing KPIs
- FastAPI and React configuration dashboard
- Browser voice bridge, HiveMind gateway, and wake-word service
- Platform-agnostic REST integration wizard
- Optional PREVENTION data export and analytics integration
- Deterministic demo manufacturing API
- Docker Compose deployment for standalone and WASABI OVOS environments

PREVENTION is optional and is not bundled as a production platform image. DocuBoT is not part of this release.

## Requirements

- Linux server or workstation
- Docker Engine 26 or newer
- Docker Compose v2
- 4 GB RAM minimum for the base stack; 8 GB recommended with PREVENTION
- 10 GB free disk space for images and build cache

## Quick start

```bash
unzip avaros-dia-v0.1.1.zip
cd avaros-dia-v0.1.1

bash scripts/prepare-env.sh
docker compose up -d --build
docker compose ps
```

The release stack uses Compose-managed container, volume, and network names.
Use `docker compose -p avaros ...` only when you want a fixed local project
name across extracted release directories.

Open `http://localhost:8080`, then enter the `AVAROS_WEB_API_KEY` stored in `.env`.

If port 8080 is occupied, set another host port before starting:

```dotenv
AVAROS_WEB_PORT=9090
HIVEMIND_WS_URL=auto
```

Then open `http://localhost:9090`. Browser voice follows the selected Web UI
port automatically; do not replace `HIVEMIND_WS_URL=auto`.

For a ready-to-test data source:

```bash
docker compose --profile demo up -d
```

In the AVAROS setup wizard, use:

- Profile name: `demo`
- API URL: `http://demo-platform:8090`
- Authentication: Bearer token
- Token: any non-empty test value

The wizard can load `wizard-preset-demo.json` when the profile is named `demo`. The demo service is intended only for evaluation and training.

## First-run configuration

The web wizard guides an operator through:

1. Platform endpoint and authentication
2. Connection test
3. Asset registration
4. Platform resource linking
5. Metric mapping
6. Intent activation
7. Optional PREVENTION configuration

AVAROS remains usable without PREVENTION; anomaly and drift commands are disabled when no PREVENTION endpoint is configured.

## Documentation

- [Installation](user-docs/INSTALLATION.md)
- [Configuration](user-docs/CONFIGURATION.md)
- [User guide](user-docs/USER-GUIDE.md)
- [Operations](user-docs/OPERATIONS.md)
- [Security](user-docs/SECURITY.md)
- [Troubleshooting](user-docs/TROUBLESHOOTING.md)
- [PREVENTION integration](user-docs/PREVENTION.md)
- [Voice commands](user-docs/VOICE-COMMANDS.md)
- [SME replication notes](user-docs/REPLICATION.md)

## Deployment modes

The root `docker-compose.yml` is the supported standalone deployment and includes its own OVOS core.

`docker/docker-compose.avaros.yml` integrates AVAROS with the WASABI OVOS Docker Compose project. It requires the external WASABI `ovos` network and the directory layout described in the installation guide.

## Support boundaries

- Platform connections must expose a reachable JSON/REST API.
- Production deployments must use HTTPS and rotate all generated credentials.
- PREVENTION authentication can use no-auth, bearer token, or Keycloak/OIDC client credentials.
- AVAROS does not provision Keycloak realms or a production PREVENTION installation.

## Verify the deployment

```bash
curl http://localhost:8080/health
docker compose ps
docker compose logs --tail=100 avaros avaros-web-ui
```

Expected health response:

```json
{"status":"ok","version":"0.1.1"}
```

## License

AVAROS is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
