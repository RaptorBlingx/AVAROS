# AVAROS D2.2 Security Checklist and Evidence

Date: 2026-07-01
Scope: AVAROS/WASABI beta package and WASABI demo deployment path
Release: AVAROS DIA OVOS Manufacturing Assistant v0.1.1

## Scope and Status

The AVAROS/WASABI beta security checklist is closed with evidence for the scoped
v0.1.1 beta package and demo deployment path. The assessment scope is limited to
the AVAROS release package, public AVAROS access point, WASABI Shop publication,
and AVAROS-related supporting services verified for this delivery. It is not a
host-wide production-security certification for unrelated services.

## Checklist

| Control | Evidence | Status |
|---|---|---|
| Release ZIP excludes secrets and runtime files | Archive scan found 384 entries and 0 forbidden `.env`, key, log, database, TLS private key, or Git metadata entries | Closed |
| Release ZIP has checksum | SHA-256: `7d3d71293c8cefe586667e021e3fceeee3b9df183a683679597a6e3ed5dfb3ff` | Closed |
| Generated environment uses private permissions | `scripts/prepare-env.sh` creates `.env` with mode `0600` | Closed |
| Live AVAROS Web UI uses HTTPS | `https://avaros.reneryo.com/health` returned HTTP 200 | Closed |
| WASABI Shop product is live over HTTPS | Product URL returned HTTP 200 | Closed |
| PREVENTION health path verified | Local PREVENTION GraphQL health query returned HTTP 200 | Closed |
| HiveMind and wake-word are not directly host-published | Configured deployment exposes them only on Docker networks | Closed |
| AVAROS direct Web UI/demo host ports are loopback-only | Web UI `127.0.0.1:8080`; demo platform `127.0.0.1:8090` | Closed |
| PREVENTION direct host port is loopback-only | PREVENTION `127.0.0.1:8082` | Closed |
| WASABI Shop origin port is restricted | Host firewall service restricts origin access to the approved proxy path | Closed |
| Default WASABI database password is blocked | Old `root/root` database login was tested and blocked | Closed |
| Current secrets absent from fresh logs | Fresh logs checked for AVAROS/HiveMind/WASABI current reusable secret values | Closed |
| HiveMind credential logging is redacted | HiveMind entrypoint patched to avoid printing reusable credentials | Closed |
| Browser audio playback uses page media | Server-backed TTS endpoint returns `audio/wav`; browser speech remains fallback | Closed |
| Clean install/uninstall verified | ZIP install, health checks, TTS WAV, demo platform, and uninstall passed in clean project | Closed |

## Evidence Summary

- AVAROS live health: HTTP 200 at `https://avaros.reneryo.com/health`.
- WASABI Shop product: HTTP 200 at the public product URL.
- PREVENTION local GraphQL health query: HTTP 200.
- Clean install test used alternate ports `19180` and `19190` and verified
  same-origin HiveMind URL resolution.
- Clean install server TTS returned `audio/wav` with a WAV `RIFF` header.
- Clean install server TTS preflight returned HTTP 204.
- Clean uninstall removed the clean-install containers, volumes, network, and
  local images.

## Exclusions

The checklist does not certify unrelated host services such as separate RENERYO
database ports or non-AVAROS services. Those require their own deployment-owner
review if they are included in a broader production audit.

## Submitted Artifacts

The D2.2 evidence set consists of:

- `AVAROS_D2.2_Beta_Package_Checklist.pdf`
- `AVAROS_D2.2_Security_Checklist_and_Evidence.pdf`
- `avaros-dia-v0.1.1.zip`
- `avaros-dia-v0.1.1.zip.sha256`
- `AVAROS-Quick-Start-v0.1.1.pdf`

The evidence set excludes raw `.env` files, credential-transfer files, runtime
logs, database backups, private keys, and screenshots containing credentials.
