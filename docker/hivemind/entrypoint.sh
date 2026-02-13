#!/bin/bash
# HiveMind-core entrypoint for AVAROS Docker deployment.
#
# 1. Writes server.json config (OVOS bus host/port, WebSocket port)
# 2. Creates a default client access key on first start
# 3. Starts the HiveMind-core listener
#
# Environment variables:
#   OVOS_BUS_HOST          — OVOS messagebus hostname (default: ovos_core)
#   OVOS_BUS_PORT          — OVOS messagebus port (default: 8181)
#   HIVEMIND_WS_PORT       — HiveMind WebSocket port (default: 5678)
#   HIVEMIND_CLIENT_NAME   — Default client name (default: avaros-web-client)
#   HIVEMIND_ACCESS_KEY    — Default client access key (default: auto-generated)
#   HIVEMIND_PASSWORD      — Default client password (default: auto-generated)

set -e

CONFIG_DIR="${HOME}/.config/hivemind-core"
CONFIG_FILE="${CONFIG_DIR}/server.json"
MARKER_FILE="${CONFIG_DIR}/.initialized"

OVOS_BUS_HOST="${OVOS_BUS_HOST:-ovos_core}"
OVOS_BUS_PORT="${OVOS_BUS_PORT:-8181}"
HIVEMIND_WS_PORT="${HIVEMIND_WS_PORT:-5678}"
HIVEMIND_CLIENT_NAME="${HIVEMIND_CLIENT_NAME:-avaros-web-client}"
HIVEMIND_ACCESS_KEY="${HIVEMIND_ACCESS_KEY:-}"
HIVEMIND_PASSWORD="${HIVEMIND_PASSWORD:-}"

echo "=== AVAROS HiveMind-core Entrypoint ==="
echo "OVOS Bus: ${OVOS_BUS_HOST}:${OVOS_BUS_PORT}"
echo "WebSocket port: ${HIVEMIND_WS_PORT}"

# --- Write server.json ---
mkdir -p "${CONFIG_DIR}"
cat > "${CONFIG_FILE}" <<EOF
{
  "agent_protocol": {
    "module": "hivemind-ovos-agent-plugin",
    "hivemind-ovos-agent-plugin": {
      "host": "${OVOS_BUS_HOST}",
      "port": ${OVOS_BUS_PORT}
    }
  },
  "binary_protocol": {
    "module": null
  },
  "network_protocol": {
    "hivemind-websocket-plugin": {
      "host": "0.0.0.0",
      "port": ${HIVEMIND_WS_PORT},
      "ssl": false
    }
  },
  "database": {
    "module": "hivemind-json-db-plugin",
    "hivemind-json-db-plugin": {
      "name": "clients",
      "subfolder": "hivemind-core"
    }
  }
}
EOF

echo "Server config written to ${CONFIG_FILE}"

# --- Create default client on first start ---
if [ ! -f "${MARKER_FILE}" ]; then
    echo "First start: creating default client '${HIVEMIND_CLIENT_NAME}'..."

    # Build the add-client command
    ADD_CMD="hivemind-core add-client --name ${HIVEMIND_CLIENT_NAME}"

    if [ -n "${HIVEMIND_ACCESS_KEY}" ]; then
        ADD_CMD="${ADD_CMD} --access-key ${HIVEMIND_ACCESS_KEY}"
    fi

    if [ -n "${HIVEMIND_PASSWORD}" ]; then
        ADD_CMD="${ADD_CMD} --password ${HIVEMIND_PASSWORD}"
    fi

    # Run add-client and capture output
    echo "Running: ${ADD_CMD}"
    ${ADD_CMD} || echo "WARNING: Failed to create default client (may already exist)"

    touch "${MARKER_FILE}"
    echo "Default client created."
else
    echo "Already initialized — skipping client creation."
fi

echo "Listing registered clients:"
hivemind-core list-clients || true

echo "=== Starting HiveMind-core listener ==="
exec hivemind-core listen
