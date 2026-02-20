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
# Keep browser/client encryption deterministic:
# - default to first 16 chars of client secret
# - normalize invalid lengths to 16 chars (AES-128)
HIVEMIND_CLIENT_CRYPTO_KEY="${HIVEMIND_CLIENT_CRYPTO_KEY:-${HIVEMIND_CLIENT_SECRET:0:16}}"
if [ -n "${HIVEMIND_CLIENT_CRYPTO_KEY}" ]; then
  KEY_LEN="${#HIVEMIND_CLIENT_CRYPTO_KEY}"
  if [ "${KEY_LEN}" -ne 16 ] && [ "${KEY_LEN}" -ne 24 ] && [ "${KEY_LEN}" -ne 32 ]; then
    HIVEMIND_CLIENT_CRYPTO_KEY="$(printf '%s' "${HIVEMIND_CLIENT_CRYPTO_KEY}" | sha256sum | cut -c1-16)"
    echo "Normalized HIVEMIND_CLIENT_CRYPTO_KEY to 16 chars for AES compatibility."
  fi
fi
HIVEMIND_CLIENT_ALLOWED_TYPES="${HIVEMIND_CLIENT_ALLOWED_TYPES:-recognizer_loop:utterance,recognizer_loop:record_begin,recognizer_loop:record_end,recognizer_loop:audio_output_start,recognizer_loop:audio_output_end,recognizer_loop:b64_transcribe,speak,speak:b64_audio,enclosure.mouth.text,mycroft.skill.handler.start,mycroft.skill.handler.complete,mycroft.audio.service.queue,mycroft.audio.service.play,mycroft.audio.service.stop,mycroft.audio.service.pause,mycroft.audio.service.resume,ovos.common_play.SEI.get.response}"

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
  echo "First start: initialization marker not found."
  touch "${MARKER_FILE}"
  echo "Initialization marker created."
else
  echo "Already initialized — marker exists."
fi

create_default_client_if_missing() {
  if [ -z "${HIVEMIND_CLIENT_KEY}" ]; then
    echo "Skipping client ensure: HIVEMIND_CLIENT_KEY is empty"
    return
  fi

  if python - <<'PY'
import os
from hivemind_core.database import ClientDatabase

key = os.environ.get("HIVEMIND_CLIENT_KEY", "")
db = ClientDatabase()
client = db.get_client_by_api_key(key) if key else None
raise SystemExit(0 if client is not None else 1)
PY
  then
    echo "Default client exists for key '${HIVEMIND_CLIENT_KEY}'."
    return
  fi

  echo "Default client missing. Creating '${HIVEMIND_CLIENT_NAME}'..."

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
}

sync_default_client_credentials() {
  if [ -z "${HIVEMIND_CLIENT_KEY}" ]; then
    echo "Skipping client sync: HIVEMIND_CLIENT_KEY is empty"
    return
  fi

  CLIENT_KEY="${HIVEMIND_CLIENT_KEY}" \
  CLIENT_NAME="${HIVEMIND_CLIENT_NAME}" \
  CLIENT_SECRET="${HIVEMIND_CLIENT_SECRET}" \
  CLIENT_CRYPTO_KEY="${HIVEMIND_CLIENT_CRYPTO_KEY}" \
  python - <<'PY'
import os
from hivemind_core.database import ClientDatabase

key = os.environ.get("CLIENT_KEY", "").strip()
name = os.environ.get("CLIENT_NAME", "").strip()
password = os.environ.get("CLIENT_SECRET", "")
crypto_raw = os.environ.get("CLIENT_CRYPTO_KEY", "").strip()
desired_crypto = crypto_raw or None

if not key:
  print("Skipping client sync: CLIENT_KEY is empty")
  raise SystemExit(0)

db = ClientDatabase()
client = db.get_client_by_api_key(key)
if client is None:
  print(f"Skipping client sync: no client found for key '{key}'")
  raise SystemExit(0)

updated = False

if name and client.name != name:
  client.name = name
  updated = True

if password and client.password != password:
  client.password = password
  updated = True

existing_crypto = client.crypto_key if client.crypto_key else None
if existing_crypto != desired_crypto:
  client.crypto_key = desired_crypto
  updated = True

if updated:
  db.update_item(client)
  db.sync()
  status = "set" if client.crypto_key else "cleared"
  print(f"Synchronized client '{client.name}' (crypto_key={status})")
else:
  print(f"Client '{client.name}' already synchronized")
PY

  CURRENT_CRYPTO_KEY="$(
    CLIENT_KEY="${HIVEMIND_CLIENT_KEY}" python - <<'PY'
import os
from hivemind_core.database import ClientDatabase

key = os.environ.get("CLIENT_KEY", "")
db = ClientDatabase()
client = db.get_client_by_api_key(key) if key else None
print((client.crypto_key if client and client.crypto_key else "").strip())
PY
  )"
  CURRENT_CRYPTO_KEY="$(echo "${CURRENT_CRYPTO_KEY}" | tail -n 1 | tr -d '\r' | xargs)"
  DESIRED_CRYPTO_KEY="$(echo "${HIVEMIND_CLIENT_CRYPTO_KEY}" | tr -d '\r' | xargs)"

  if [ -z "${DESIRED_CRYPTO_KEY}" ]; then
    echo "Client crypto_key is intentionally disabled; skipping recreate enforcement."
  elif [ "${CURRENT_CRYPTO_KEY}" != "${DESIRED_CRYPTO_KEY}" ]; then
    echo "Client crypto_key mismatch after sync (desired='${DESIRED_CRYPTO_KEY:-<empty>}' current='${CURRENT_CRYPTO_KEY:-<empty>}'). Recreating client..."

    CLIENT_NODE_ID="$(
      CLIENT_KEY="${HIVEMIND_CLIENT_KEY}" python - <<'PY'
import os
from hivemind_core.database import ClientDatabase

key = os.environ.get("CLIENT_KEY", "")
db = ClientDatabase()
client = db.get_client_by_api_key(key) if key else None
print(client.client_id if client else "")
PY
    )"
    CLIENT_NODE_ID="$(echo "${CLIENT_NODE_ID}" | tail -n 1 | tr -d '\r' | xargs)"

    if [ -n "${CLIENT_NODE_ID}" ]; then
      hivemind-core delete-client "${CLIENT_NODE_ID}" >/dev/null || true
    fi

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
    if "${ADD_CMD[@]}" >/dev/null; then
      echo "Client recreated with desired crypto_key policy."
    else
      echo "WARNING: Failed to recreate client with desired crypto_key policy."
    fi
  fi
}

create_default_client_if_missing
sync_default_client_credentials

# --- Ensure configured client exists on every startup ---
if [ -n "${HIVEMIND_CLIENT_KEY}" ]; then
  if CLIENT_KEY="${HIVEMIND_CLIENT_KEY}" python - <<'PY'
import os
from hivemind_core.database import ClientDatabase

key = os.environ.get("CLIENT_KEY", "")
db = ClientDatabase()
client = db.get_client_by_api_key(key) if key else None
raise SystemExit(0 if client is not None else 1)
PY
  then
    echo "Configured client key already exists in database."
  else
    echo "Configured client key not found — recreating client '${HIVEMIND_CLIENT_NAME}'."
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

    "${ADD_CMD[@]}" || echo "WARNING: Failed to recreate configured client"
  fi
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

  # Enforce with CLI as well; hivemind-core authoritative policy path.
  CLIENT_NODE_ID="$(
    CLIENT_KEY="${HIVEMIND_CLIENT_KEY}" python - <<'PY'
import os
from hivemind_core.database import ClientDatabase

key = os.environ.get("CLIENT_KEY", "")
db = ClientDatabase()
client = db.get_client_by_api_key(key) if key else None
print(client.client_id if client else "")
PY
  )"
  CLIENT_NODE_ID="$(echo "${CLIENT_NODE_ID}" | tail -n 1 | tr -d '\r' | xargs)"

  if [ -n "${CLIENT_NODE_ID}" ]; then
    OLD_IFS="$IFS"
    IFS=','
    for msg_type in ${HIVEMIND_CLIENT_ALLOWED_TYPES}; do
      trimmed="$(echo "${msg_type}" | xargs)"
      if [ -n "${trimmed}" ]; then
        hivemind-core allow-msg "${trimmed}" "${CLIENT_NODE_ID}" >/dev/null || true
      fi
    done
    IFS="$OLD_IFS"
    echo "Applied allow-msg policy to node '${CLIENT_NODE_ID}'"
  else
    echo "Skipping allow-msg policy: client node id not found"
  fi
fi

echo "Listing registered clients:"
hivemind-core list-clients || true

echo "=== Starting HiveMind-core listener ==="
exec hivemind-core listen
