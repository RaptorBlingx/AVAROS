#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.avaros.yml"
SERVICE="avaros-web-ui"
PROXY_CONTAINER="avaros-proxy"
PROXY_NETWORK="ovos"

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ docker is not installed or not in PATH"
  exit 1
fi

echo "[1/5] Rebuilding ${SERVICE} image (no cache) using ${COMPOSE_FILE}"
docker compose -f "$COMPOSE_FILE" build --no-cache "$SERVICE"

echo "[2/5] Recreating ${SERVICE} without touching dependencies"
docker rm -f "$SERVICE" >/dev/null 2>&1 || true
docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate "$SERVICE"

echo "[3/5] Ensuring ${SERVICE} is attached to '${PROXY_NETWORK}' network"
if ! docker inspect -f '{{json .NetworkSettings.Networks}}' "$SERVICE" | grep -q '"ovos"'; then
  docker network connect "$PROXY_NETWORK" "$SERVICE" || true
fi

echo "[4/5] Verifying proxy DNS resolution"
docker exec "$PROXY_CONTAINER" getent hosts "$SERVICE" >/dev/null

echo "[5/5] Verifying health"
for _ in $(seq 1 20); do
  status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$SERVICE" 2>/dev/null || true)"
  if [[ "$status" == "healthy" || "$status" == "running" ]]; then
    break
  fi
  sleep 2
done

docker exec "$PROXY_CONTAINER" sh -lc "wget -qO- --no-check-certificate https://127.0.0.1/health >/dev/null || wget -qO- http://127.0.0.1/health >/dev/null"

echo "✅ Web UI rebuild complete and reachable"
echo "   - In-container health: http://localhost:8080/health"
echo "   - Public URL (via nginx): https://avaros.int.arti.ac"
