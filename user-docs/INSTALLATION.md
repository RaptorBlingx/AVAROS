# AVAROS installation

This guide installs AVAROS on a single Linux server with Docker Compose.

## 1. Prepare the server

Minimum:

- Docker Engine 26+
- Docker Compose v2
- 4 GB RAM and 10 GB free disk space
- One available TCP port for the Web UI; the default is 8080

For an internet-facing deployment, use a domain, HTTPS reverse proxy, firewall, and at least 8 GB RAM.

Verify Docker:

```bash
docker version
docker compose version
```

## 2. Unpack and configure

```bash
unzip avaros-dia-v0.1.1.zip
cd avaros-dia-v0.1.1
bash scripts/prepare-env.sh
```

The script creates a private `.env` file with generated API and HiveMind credentials. Do not share or upload this file.

Review the values:

```bash
chmod 600 .env
editor .env
```

Set `TZ` and change host ports if they conflict with other services.

For example, when port 8080 is occupied:

```dotenv
AVAROS_WEB_PORT=9090
HIVEMIND_WS_URL=auto
```

`HIVEMIND_WS_URL=auto` makes browser voice use the same host and port as the
Web UI, such as `ws://localhost:9090/hivemind/`.

For a reverse-proxy deployment, bind direct service ports to localhost:

```dotenv
AVAROS_WEB_BIND_ADDRESS=127.0.0.1
AVAROS_DEMO_BIND_ADDRESS=127.0.0.1
```

## 3. Start AVAROS

```bash
docker compose up -d --build
docker compose ps
```

The release uses Compose-managed container, volume, and network names. Do not
add fixed `container_name` or global volume/network names; Compose-managed
names allow clean test installs even when another AVAROS instance exists.

Wait until the skill, message bus, OVOS core, wake-word service, HiveMind, and web UI are healthy.

Check the web API:

```bash
curl http://localhost:8080/health
```

Open `http://SERVER_IP:8080` and sign in with `AVAROS_WEB_API_KEY` from `.env`.

## 4. Start the demo platform

The optional demo API provides deterministic manufacturing data:

```bash
docker compose --profile demo up -d
curl http://localhost:8090/health
```

Configure the wizard with:

- Profile name: `demo`
- API URL: `http://demo-platform:8090`
- Authentication: Bearer
- Token: any non-empty test token

Load the available preset to populate assets, mappings, and resource links. Do not use the demo profile as a production data source.

## 5. Configure a remote server

When users open AVAROS from another computer:

1. Put AVAROS behind an HTTPS reverse proxy.
2. Proxy `/` to `avaros-web-ui:8080`.
3. Preserve WebSocket upgrade headers for `/hivemind/`; the supplied Nginx
   configuration proxies that route to `avaros-hivemind:5678`.
4. Keep `HIVEMIND_WS_URL=auto`.
5. Restrict direct host access to the Web UI port; HiveMind and wake-word
   services should remain private to the Docker network in the standalone stack.

The supplied Nginx configurations under `docker/nginx/` are reference configurations. Replace test certificates with certificates issued for your domain.

## 6. Optional PREVENTION integration

AVAROS works without PREVENTION. Only enable it when a PREVENTION service and its access details are available.

The local no-auth compose file requires the upstream PREVENTION source or image and is intended for controlled evaluation:

```bash
PREVENTION_BUILD_CONTEXT=/path/to/prevention \
docker compose -f docker/docker-compose.prevention.yml up -d
```

Then set:

```dotenv
PREVENTION_URL=http://prevention:8081
PREVENTION_EXPORT_ENABLED=true
```

Restart AVAROS after environment changes:

```bash
docker compose up -d --force-recreate avaros avaros-web-ui avaros-prevention-exporter
```

## 7. WASABI OVOS integration

Use `docker/docker-compose.avaros.yml` only when the WASABI OVOS stack is already installed and its external Docker network is named `ovos`.

```bash
docker network inspect ovos
docker compose -f docker/docker-compose.avaros.yml up -d
```

## 8. Stop or remove

Stop containers while keeping data:

```bash
docker compose stop
```

Remove containers while keeping named volumes:

```bash
docker compose down
```

Delete all AVAROS data only when intentionally resetting the installation:

```bash
bash scripts/uninstall.sh
```

The script also removes the optional PREVENTION or WASABI integration variant
when Docker labels show that it was started from this same extracted release.

On a disposable test machine, also remove every image referenced by AVAROS:

```bash
bash scripts/uninstall.sh --all-images
cd ..
rm -rf avaros-dia-v0.1.1
```

The `--all-images` option can remove images shared with another Compose
project. Use it only when this machine is dedicated to the AVAROS test.
