#!/bin/bash
# HiveMind-core entrypoint for AVAROS Docker deployment.
#
# 1. Writes server.json config (OVOS bus host/port, WebSocket port)
# 2. Creates a default client access key on first start
# 3. Starts the HiveMind-core listener
#
# Environment variables:
#   OVOS_BUS_HOST          — OVOS messagebus hostname (default: ovos_messagebus)
#   OVOS_BUS_PORT          — OVOS messagebus port (default: 8181)
#   HIVEMIND_WS_PORT       — HiveMind WebSocket port (default: 5678)
#   HIVEMIND_MASTER_KEY    — Reserved master/admin key (task contract)
#   HIVEMIND_CLIENT_NAME   — Default client name (default: avaros-web-client)
#   HIVEMIND_CLIENT_KEY    — Default client access key
#   HIVEMIND_CLIENT_SECRET — Default client password/secret
#   HIVEMIND_CLIENT_CRYPTO_KEY — Default client crypto key for WS payload encryption

set -e

CONFIG_DIR="${HOME}/.config/hivemind-core"
CONFIG_FILE="${CONFIG_DIR}/server.json"
MARKER_FILE="${CONFIG_DIR}/.initialized"

OVOS_BUS_HOST="${OVOS_BUS_HOST:-ovos_messagebus}"
OVOS_BUS_PORT="${OVOS_BUS_PORT:-8181}"
HIVEMIND_WS_PORT="${HIVEMIND_WS_PORT:-5678}"
HIVEMIND_MASTER_KEY="${HIVEMIND_MASTER_KEY:-avaros-dev-key-change-in-production}"
HIVEMIND_CLIENT_NAME="${HIVEMIND_CLIENT_NAME:-avaros-web-client}"
HIVEMIND_CLIENT_KEY="${HIVEMIND_CLIENT_KEY:-avaros-dev-key}"
HIVEMIND_CLIENT_SECRET="${HIVEMIND_CLIENT_SECRET:-avaros-dev-secret}"
HIVEMIND_CLIENT_CRYPTO_KEY="${HIVEMIND_CLIENT_CRYPTO_KEY:-}"
HIVEMIND_CLIENT_ALLOWED_TYPES="${HIVEMIND_CLIENT_ALLOWED_TYPES:-recognizer_loop:utterance,recognizer_loop:record_begin,recognizer_loop:record_end,recognizer_loop:audio_output_start,recognizer_loop:audio_output_end,recognizer_loop:b64_transcribe,speak:b64_audio,ovos.common_play.SEI.get.response}"

echo "=== AVAROS HiveMind-core Entrypoint ==="
echo "OVOS Bus: ${OVOS_BUS_HOST}:${OVOS_BUS_PORT}"
echo "WebSocket port: ${HIVEMIND_WS_PORT}"
echo "Master key configured: yes"

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

  # Build the add-client command safely as argv array
  ADD_CMD=("hivemind-core" "add-client" "--name" "${HIVEMIND_CLIENT_NAME}")

  if [ -n "${HIVEMIND_CLIENT_KEY}" ]; then
    ADD_CMD+=("--access-key" "${HIVEMIND_CLIENT_KEY}")
    fi

  if [ -n "${HIVEMIND_CLIENT_SECRET}" ]; then
    ADD_CMD+=("--password" "${HIVEMIND_CLIENT_SECRET}")
    fi

  if [ -n "${HIVEMIND_CLIENT_CRYPTO_KEY}" ]; then
    ADD_CMD+=("--crypto-key" "${HIVEMIND_CLIENT_CRYPTO_KEY}")
    fi

  echo "Running: hivemind-core add-client --name ${HIVEMIND_CLIENT_NAME} [...redacted...]"
  "${ADD_CMD[@]}" || echo "WARNING: Failed to create default client (may already exist)"

    touch "${MARKER_FILE}"
    echo "Default client created."
else
    echo "Already initialized — skipping client creation."
fi

# --- Ensure client policy is consistent on every startup ---
if [ -n "${HIVEMIND_CLIENT_KEY}" ] && [ -n "${HIVEMIND_CLIENT_ALLOWED_TYPES}" ]; then
  echo "Applying allowed_types policy for client key '${HIVEMIND_CLIENT_KEY}'..."
  CLIENT_KEY="${HIVEMIND_CLIENT_KEY}" \
  CLIENT_ALLOWED_TYPES="${HIVEMIND_CLIENT_ALLOWED_TYPES}" \
  python - <<'PY'
import os
from hivemind_core.database import ClientDatabase


def parse_allowed_types(raw: str) -> list[str]:
  return [item.strip() for item in raw.split(",") if item.strip()]


db = ClientDatabase()
key = os.environ.get("CLIENT_KEY", "")
allowed_raw = os.environ.get("CLIENT_ALLOWED_TYPES", "")
allowed_types = parse_allowed_types(allowed_raw)

if not key:
  print("Skipping policy update: CLIENT_KEY is empty")
elif not allowed_types:
  print("Skipping policy update: CLIENT_ALLOWED_TYPES is empty")
else:
  client = db.get_client_by_api_key(key)
  if client is None:
    print(f"Skipping policy update: no client found for key '{key}'")
  else:
    client.allowed_types = allowed_types
    db.update_item(client)
    db.sync()
    print(f"Updated allowed_types for client '{client.name}' ({len(allowed_types)} types)")
PY
fi

echo "Listing registered clients:"
hivemind-core list-clients || true

echo "=== Starting HiveMind-core listener ==="
exec hivemind-core listen
