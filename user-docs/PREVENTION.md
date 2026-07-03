# PREVENTION integration

PREVENTION is an optional analytics backend for AVAROS anomaly and drift monitoring.

## Supported scope

AVAROS can:

- export mapped KPI time-series data;
- report export freshness;
- query anomaly results;
- query drift results;
- authenticate with no-auth, bearer token, or Keycloak/OIDC client credentials.

AVAROS does not bundle a production PREVENTION image, provision Keycloak, or claim the full PREVENTION predictive and prescriptive portfolio.

## Enable

Set or enter through the wizard:

```dotenv
PREVENTION_URL=https://prevention.example.com
PREVENTION_AUTH_MODE=keycloak_client_credentials
PREVENTION_KEYCLOAK_TOKEN_URL=https://identity.example.com/realms/wasabi/protocol/openid-connect/token
PREVENTION_KEYCLOAK_CLIENT_ID=avaros-client
PREVENTION_KEYCLOAK_CLIENT_SECRET=CHANGE_ME
PREVENTION_KEYCLOAK_SCOPE=openid
PREVENTION_EXPORT_ENABLED=true
```

Restart affected services after environment changes.

## Data freshness

The exporter writes PREVENTION input files and an `export_manifest.json`. AVAROS marks the feed stale when it exceeds `PREVENTION_DATA_MAX_AGE_MINUTES`.

Connection health and data freshness are separate states. A reachable endpoint may still have missing or stale input data.

## Disable

```dotenv
PREVENTION_URL=
PREVENTION_EXPORT_ENABLED=false
```

AVAROS continues to provide configured KPI, trend, and comparison functions without PREVENTION.
