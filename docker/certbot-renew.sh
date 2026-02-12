#!/bin/bash
# Certbot certificate renewal for AVAROS production
#
# Renews Let's Encrypt certificates and reloads Nginx to pick up
# the new certs. Run via cron monthly:
#
#   0 0 1 * * /path/to/certbot-renew.sh
#
# Prerequisites:
#   - Docker Compose stack running with avaros-proxy service
#   - Certbot container configured in docker-compose.avaros.yml (production)
#   - Valid domain pointing to this server

set -euo pipefail

COMPOSE_DIR="$(dirname "$0")"

echo "[$(date)] Starting certificate renewal..."

docker compose -f "$COMPOSE_DIR/docker-compose.avaros.yml" \
    run --rm certbot renew --quiet

docker compose -f "$COMPOSE_DIR/docker-compose.avaros.yml" \
    exec avaros-proxy nginx -s reload

echo "[$(date)] Certificate renewal complete."
