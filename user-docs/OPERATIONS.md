# AVAROS operations

## Service lifecycle

```bash
docker compose up -d
docker compose ps
docker compose restart
docker compose stop
docker compose down
```

Do not use `down -v` unless all persistent AVAROS data should be deleted.

For a complete AVAROS-only reset:

```bash
bash scripts/uninstall.sh
```

Optional PREVENTION and WASABI integration services are included only when
their Docker Compose labels point to this release directory.

## Health checks

```bash
curl http://localhost:8080/health
curl http://localhost:8080/wakeword/health
docker compose ps
```

Review application status with:

```bash
curl http://localhost:8080/api/v1/status \
  -H "X-API-Key: ${AVAROS_WEB_API_KEY}"
```

## Logs

```bash
docker compose logs --tail=200 avaros
docker compose logs --tail=200 avaros-web-ui
docker compose logs --tail=200 hivemind
docker compose logs --tail=200 avaros-prevention-exporter
```

Never publish logs without reviewing them for URLs, identifiers, or authorization data.

## Backup

The standalone deployment stores AVAROS settings in the
`avaros_avaros-data` Docker volume.

```bash
mkdir -p backups
docker compose stop avaros avaros-web-ui avaros-prevention-exporter
docker run --rm \
  -v avaros_avaros-data:/data:ro \
  -v "$PWD/backups":/backup \
  alpine sh -c 'tar czf /backup/avaros-data.tgz -C /data .'
docker compose start avaros avaros-web-ui avaros-prevention-exporter
```

Store `.env` separately in a secure secret backup.

## Restore

On an empty `avaros_avaros-data` volume:

```bash
docker compose down
docker run --rm \
  -v avaros_avaros-data:/data \
  -v "$PWD/backups":/backup:ro \
  alpine sh -c 'tar xzf /backup/avaros-data.tgz -C /data'
docker compose up -d
```

## Upgrade

1. Back up the data volume and `.env`.
2. Read `CHANGELOG.md`.
3. Replace application files with the new release.
4. Keep the existing `.env`.
5. Rebuild and verify:

```bash
docker compose build --pull
docker compose up -d
docker compose ps
```

## Capacity

Recommended:

- base stack: 4 GB RAM minimum
- base stack plus local PREVENTION: 8 GB RAM minimum
- swap configured on small virtual machines
- Docker disk usage monitored regularly

Check:

```bash
free -h
df -h
docker system df
```
