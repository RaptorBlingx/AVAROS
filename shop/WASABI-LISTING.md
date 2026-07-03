# WASABI Shop listing — AVAROS

## Product setup

| Field | Value |
|---|---|
| Product name | AVAROS DIA — OVOS Assistant for Sustainable Manufacturing |
| Product type | Virtual product |
| Category | Skills |
| Version | 0.1.1 |
| License | Apache-2.0 |
| Price | Free download |
| Reference | AVAROS-DIA-0.1.1 |
| Download file | `avaros-dia-v0.1.1.zip` |

## Short description

Dockerized OVOS Digital Intelligent Assistant for voice-driven manufacturing KPI queries, comparisons, trends, and optional PREVENTION anomaly and drift analytics.

## Long description

AVAROS helps manufacturing teams access operational sustainability information through voice and web interfaces. Operators can query energy, production, material, carbon, and supplier KPIs; compare assets; review trends; and, when PREVENTION is connected, request anomaly and drift analysis.

The downloadable package includes the AVAROS OVOS skill, a FastAPI/React configuration dashboard, Docker Compose deployment, browser voice and wake-word services, a platform-agnostic REST integration wizard, deterministic demo data, configuration templates, and operator documentation.

AVAROS is designed for replication at manufacturing SMEs. A site administrator can connect a compatible REST API, register assets, link platform resources, map canonical metrics, test each mapping, and activate only supported voice intents.

PREVENTION is optional. A production PREVENTION image and Keycloak deployment are not bundled. DocuBoT is outside the scope of version 0.1.1.

## Key features

- Docker Compose installation
- OVOS conversational assistant
- 19 canonical manufacturing KPIs
- Energy, production, material, carbon, and supplier domains
- Asset comparison and time-series trends
- FastAPI/React setup wizard
- Multiple platform profiles
- Browser voice, HiveMind, and wake-word services
- Dynamic same-origin HiveMind proxy that follows custom Web UI ports
- Optional PREVENTION anomaly and drift analytics
- Deterministic demo manufacturing API
- Sample production CSV
- Installation, configuration, operations, security, and replication guides

## Requirements

- Linux server
- Docker Engine 26+
- Docker Compose v2
- 4 GB RAM minimum; 8 GB recommended with PREVENTION
- 10 GB free disk space
- HTTPS domain and reverse proxy for remote browser voice
- Compatible manufacturing JSON/REST API for live KPI data

## Included files

- `README.md`
- `LICENSE`
- `CHANGELOG.md`
- `.env.example`
- `docker-compose.yml`
- `skill/`
- `web-ui/`
- `services/`
- `docker/`
- `tools/`
- `examples/`
- `user-docs/`
- `scripts/prepare-env.sh`
- `scripts/uninstall.sh`

## Support and scope

Support is provided through the seller contact channel on the WASABI Shop product page.

Implemented in 0.1.1:

- KPI, trend, and comparison queries
- platform configuration and metric mapping
- anomaly and drift result queries through PREVENTION
- deployment and replication documentation

Not bundled:

- manufacturing source platform
- production PREVENTION image
- Keycloak realm or user provisioning
- DocuBoT
- private RENERYO services or pilot data

## SEO

Meta title: `AVAROS OVOS Manufacturing Digital Assistant`

Meta description: `Deploy AVAROS, a Dockerized OVOS assistant for manufacturing KPIs, sustainability metrics, voice interaction, and optional PREVENTION analytics.`

Keywords:

`AVAROS, OVOS, OpenVoiceOS, manufacturing, digital intelligent assistant, sustainability, KPI, energy, OEE, carbon, PREVENTION, WASABI`

## Attachments

- Installation guide
- Configuration guide
- Security guide
- Voice command reference
- SME replication notes
- Apache-2.0 license
- SHA-256 checksum

## Product images

1. AVAROS product cover
2. Setup wizard platform connection
3. Asset and metric mapping
4. System status
5. Voice assistant
6. PREVENTION configuration/status

Screenshots must contain demo data only and must not show API keys, cookies, internal hostnames, customer data, or browser authorization URLs.
