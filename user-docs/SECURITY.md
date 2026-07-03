# AVAROS security guide

Complete this checklist before exposing AVAROS to the internet.

## Required controls

- Use HTTPS with a certificate issued for the deployment domain.
- Generate `.env` with `scripts/prepare-env.sh`.
- Keep `.env`, private keys, database files, and logs out of the release archive.
- Restrict direct access to the configured Web UI port and optional demo port.
- Allow the public to reach only the HTTPS reverse proxy.
- Keep Docker and the host operating system patched.
- Back up and test restoration of the AVAROS data volume.
- Use a dedicated service account with minimum platform permissions.
- Rotate credentials after personnel, environment, or exposure changes.

## Reverse proxy

The supplied Nginx configuration:

- blocks hidden files and repository metadata;
- forwards HiveMind authorization as an internal header;
- removes the authorization query string before proxying;
- disables access logging for the HiveMind WebSocket route.

Do not serve a Git working tree directly from a web document root.

## Secret handling

Never include:

- `.env`
- API keys or bearer tokens
- platform session cookies
- HiveMind credentials
- Keycloak client secrets
- TLS private keys
- production databases or exported logs

The release builder rejects common secret and runtime file types.

## Credential rotation

To rotate AVAROS and HiveMind credentials:

1. Back up `.env`.
2. Run `bash scripts/prepare-env.sh --force`.
3. Restore any non-secret site-specific settings from the backup.
4. Recreate the web UI and HiveMind services:

```bash
docker compose up -d --force-recreate avaros-web-ui hivemind
```

5. Sign in with the new API key and verify voice connectivity.

## Platform data

AVAROS should have read-only access when only KPI queries are required. Enable control actions only after a separate authorization and safety assessment.

Do not use private pilot or personal data in public screenshots, examples, or shop attachments.

## Reporting a vulnerability

Do not disclose sensitive findings in a public issue. Contact the AVAROS distributor or support contact shown on the WASABI Shop product page.
