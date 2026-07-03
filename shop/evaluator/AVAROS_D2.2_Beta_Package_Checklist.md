# AVAROS D2.2 Beta Package Checklist

Date: 2026-07-01
Release: AVAROS DIA OVOS Manufacturing Assistant v0.1.1
WASABI deliverable: D2.2 Beta package + security checklist

## Scope and Status

The AVAROS/WASABI beta package is ready for evaluator review for the scoped
v0.1.1 package. The installable ZIP, checksum, quick-start material, shop
listing, and public AVAROS access point have been prepared and verified.

This checklist applies to the AVAROS v0.1.1 beta package and its configured
demo deployment. It does not certify unrelated host services.

## Evaluator Artifacts

| Artifact | File or URL | Status |
|---|---|---|
| Release ZIP | `avaros-dia-v0.1.1.zip` | Ready |
| SHA-256 checksum | `avaros-dia-v0.1.1.zip.sha256` | Ready |
| Quick-start PDF | `AVAROS-Quick-Start-v0.1.1.pdf` | Ready |
| Security checklist PDF | `AVAROS_D2.2_Security_Checklist_and_Evidence.pdf` | Ready |
| WASABI Shop product | `https://shop.reneryo.com/skills/38-avaros-dia-ovos-manufacturing-assistant.html` | Live |
| AVAROS demo URL | `https://avaros.reneryo.com` | Live |

## Package Contents

| Expected beta content | Evidence |
|---|---|
| Docker Compose standalone deployment | Packaged as `docker-compose.yml` inside the ZIP |
| OVOS skill | Packaged under `skill/` |
| Web UI and embedded widget source | Packaged under `web-ui/`; Docker build creates the UI and widget bundles |
| HiveMind WebSocket proxy | Packaged under `docker/hivemind/` and composed as a private Docker-network service |
| Wake-word backend | Packaged under `services/wakeword/` |
| Deterministic demo data platform | Packaged under `tools/reneryo-data-generator/` and enabled with `--profile demo` |
| User documentation | Packaged under `user-docs/` |
| Environment template | `.env.example` included; generated `.env` is not included |
| License and changelog | `LICENSE` and `CHANGELOG.md` included |

## Verification

| Check | Result |
|---|---|
| Release ZIP rebuilt on 2026-07-01 | Passed |
| SHA-256 generated | `b17676a3972209ca75754139aa148a012230af6427bd942c813afde24789199b` |
| Archive forbidden-file scan | 0 `.env`, key, log, database, TLS private key, or Git metadata entries |
| Packaged Compose validation | `docker compose config --quiet` passed |
| Fixed container names removed from packaged Compose | Passed |
| Global network/volume names removed from packaged Compose | Passed |
| Clean install from ZIP on alternate ports | Passed |
| Web UI health in clean install | HTTP 200 |
| Same-origin HiveMind URL in clean install | `ws://localhost:19180/hivemind/` |
| Server-backed TTS response in clean install | `audio/wav`, WAV header `RIFF` |
| Server-backed TTS preflight in clean install | HTTP 204 |
| Demo platform health in clean install | HTTP 200 |
| Clean uninstall | Removed clean-install containers, volumes, network, and local images |
