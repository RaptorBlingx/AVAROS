# Changelog

All notable changes to AVAROS are documented here.

## 0.1.1 - 2026-06-22

- Made the HiveMind browser endpoint follow the active Web UI origin and port.
- Added a same-origin WebSocket proxy so custom ports such as 9090 work
  without hardcoded browser or Docker-internal addresses.
- Added a scoped uninstall script for clean end-user installation testing.
- Scoped standalone container, volume, and network names to a stable `avaros`
  Compose project so installs and upgrades from differently named release
  directories do not conflict.
- Kept HiveMind and wake-word ports internal; browser access uses the Web UI
  proxy, reducing host-port conflicts.

## 0.1.0 - 2026-06-22

- Added the Dockerized AVAROS OVOS skill and standalone stack.
- Added the FastAPI/React configuration dashboard.
- Added platform profiles, assets, resource linking, and metric mapping.
- Added 19 canonical manufacturing KPI intents.
- Added browser voice, HiveMind, and wake-word services.
- Added optional PREVENTION anomaly and drift integration.
- Added deterministic demo platform data.
- Added customer installation, configuration, operations, security, and replication documentation.
- Added a clean WASABI Shop release builder that excludes non-runtime development material.
