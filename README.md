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
- English (`en-US`) and Turkish (`tr-TR`) OVOS voice support
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
AVAROS is deterministic, advisory, and read-only. It does not control equipment, infer process-parameter causality without a configured model, or judge performance without a configured objective.

## Language selection

English remains the default. Select Turkish (`tr-TR`) under **Settings → Voice → Language**
to use Turkish speech recognition, OVOS intents, responses, and text-to-speech.
Embeddable widgets can opt in with `data-language="tr-TR"` on the widget script;
omitting the attribute keeps the existing English behavior.

## Documentation

- [Reneryo technical handover](docs/RENERYO-TECHNICAL-HANDOVER.md)
- [System architecture](docs/SYSTEM-ARCHITECTURE.md)
- [AVAROS API reference](docs/AVAROS-API-REFERENCE.md)
- [Intents and dialogue contract](docs/INTENTS-AND-DIALOGUE.md)
- [Data lifecycle and query pipeline](docs/DATA-LIFECYCLE.md)
- [Alerts and notification boundary](docs/ALERTS-AND-NOTIFICATIONS.md)
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

### Organization-local periods and observation timestamps

For signed Reneryo widget requests, calendar periods require an administrator-verified
organization/timezone binding in the active profile's `extra_settings`:

```json
{"organization_timezones": {"verified-organization-id": "Europe/Istanbul"}}
```

Verify the organization ID and its IANA timezone before setting this metadata.
Reneryo's current organization schema does not expose a timezone field. AVAROS does
not infer this binding from language, browser timezone, hostname, or `site_timezone`.
Missing/invalid bindings clarify local-date requests; rolling elapsed-day windows
and latest observations do not require a local calendar. Unsigned native profiles
retain their existing `site_timezone` behavior. This code change does not configure
or deploy a binding for any real organization.

The same verified binding renders observation timestamps in display and speech,
including local date changes. Display includes the IANA zone and UTC offset;
speech expands the date/zone. Missing or invalid bindings keep explicit UTC,
and naive source times are never assigned a guessed timezone. Source timestamps,
evidence, requested UTC bounds and monthly bucket labels remain unchanged.
See [controlled FutureGen MVP acceptance](docs/FUTUREGEN-MVP-ACCEPTANCE.md) for
deployment prerequisites, rollback and the real text/audio acceptance boundary.

Calendar boundaries use one request clock and are sent as UTC instants. Reneryo
owns aggregation: AVAROS selects its existing history resolution and never prorates
buckets. Meter windows that do not align with Reneryo's automatically selected
buckets cannot establish exact local consumption; AVAROS reports that limitation.
Meter values remain separate, including compatible meters that could overlap.
Explicit empty windows do not fetch a different historical period.

Spoken cardinal numbers are parsed only in duration/percentage expressions in the
existing request handlers. Unsupported or ambiguous quantities clarify. The widget
uses the same grounded reply's display headline and speech text, with bounded
inventory narration and an expandable full name list. Actual STT/TTS listening
acceptance remains separate from the automated text and signed-transport tests.

## License

AVAROS is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
