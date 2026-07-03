# AVAROS troubleshooting

## A container is not healthy

```bash
docker compose ps
docker compose logs --tail=200 SERVICE_NAME
docker inspect SERVICE_NAME --format '{{json .State}}'
```

Common causes are insufficient memory, occupied ports, missing `.env`, and an unreachable dependency.

## Web UI does not open

```bash
curl http://localhost:8080/health
ss -lntp | grep 8080
docker compose logs --tail=200 avaros-web-ui
```

Check `AVAROS_WEB_PORT` and host firewall rules.

## API key is rejected

Confirm the key in `.env`, then recreate the web UI:

```bash
docker compose up -d --force-recreate avaros-web-ui
```

Enter the exact value of `AVAROS_WEB_API_KEY`.

## Platform connection fails

- Use a URL reachable from inside the container.
- Do not use `localhost` for a service on another host.
- Verify DNS, TLS certificates, authentication, and the API base path.
- Test from the web UI container:

```bash
docker compose exec avaros-web-ui python -c \
  "import urllib.request; print(urllib.request.urlopen('https://PLATFORM/health').status)"
```

## Voice does not connect

- Confirm HiveMind is healthy.
- Keep `HIVEMIND_WS_URL=auto`; the browser should show the same host and port
  used to open the Web UI, followed by `/hivemind/`.
- Rebuild the Web UI after upgrading from AVAROS 0.1.0.
- For remote access, configure HTTPS and preserve WebSocket upgrade headers.
- Confirm the browser and server use matching HiveMind client and crypto keys.

```bash
docker compose up -d --build --force-recreate avaros-web-ui
docker compose logs --tail=200 hivemind
docker compose logs --tail=200 avaros-web-ui
```

## Wake word does not respond

```bash
curl http://localhost:8080/wakeword/health
docker compose logs --tail=200 avaros-wakeword
```

Check browser microphone permission and use HTTPS for remote browser access.

## PREVENTION is unavailable

AVAROS remains operational without PREVENTION. Confirm:

- `PREVENTION_URL`
- authentication mode
- endpoint reachability
- fresh export manifest
- PREVENTION logs

Disable PREVENTION until the external service is ready.
