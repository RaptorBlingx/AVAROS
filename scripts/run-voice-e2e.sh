#!/bin/bash
# =================================================================
# AVAROS Voice E2E Pipeline Tests
#
# Self-contained CI script that:
#   1. Builds all Docker images (base E2E + HiveMind overlay)
#   2. Starts the full voice stack (messagebus, skill, DB,
#      mock RENERYO, HiveMind)
#   3. Waits for services to become healthy
#   4. Runs pytest inside the e2e-runner container
#   5. Collects logs on failure
#   6. Tears everything down
#
# Usage:
#   ./scripts/run-voice-e2e.sh
#   ./scripts/run-voice-e2e.sh --keep   # Keep containers after tests
# =================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_COMPOSE="$PROJECT_ROOT/docker/docker-compose.e2e.yml"
VOICE_COMPOSE="$PROJECT_ROOT/docker/docker-compose.e2e-voice.yml"
KEEP_CONTAINERS=false
BUILD_RETRIES=2
READINESS_RETRIES=30
READINESS_INTERVAL=2

if [[ "${1:-}" == "--keep" ]]; then
    KEEP_CONTAINERS=true
fi

COMPOSE_CMD=(docker compose -f "$BASE_COMPOSE" -f "$VOICE_COMPOSE")
EXIT_CODE=0
STACK_STARTED=false

echo "=== AVAROS Voice E2E Pipeline Tests ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# ── Cleanup function ─────────────────────────────────────
cleanup() {
    if [[ "$KEEP_CONTAINERS" == "false" ]]; then
        echo ""
        echo "Tearing down containers..."
        "${COMPOSE_CMD[@]}" down -v --remove-orphans 2>/dev/null || true
    else
        echo ""
        echo "Keeping containers running (--keep flag)."
        echo "Tear down manually: ${COMPOSE_CMD[*]} down -v"
    fi
}
trap cleanup EXIT

collect_logs() {
    echo ""
    echo "=== docker compose status ==="
    "${COMPOSE_CMD[@]}" ps --format "table {{.Name}}\t{{.Status}}" || true
    echo ""
    echo "=== avaros-skill logs ==="
    "${COMPOSE_CMD[@]}" logs --tail=100 avaros-skill || true
    echo ""
    echo "=== ovos-messagebus logs ==="
    "${COMPOSE_CMD[@]}" logs --tail=60 ovos_messagebus || true
    echo ""
    echo "=== hivemind logs ==="
    "${COMPOSE_CMD[@]}" logs --tail=80 hivemind || true
    echo ""
    echo "=== reneryo-data-generator logs ==="
    "${COMPOSE_CMD[@]}" logs --tail=60 reneryo-data-generator || true
}

build_images() {
    local attempt
    for attempt in $(seq 1 "$BUILD_RETRIES"); do
        echo "Building Docker images (attempt ${attempt}/${BUILD_RETRIES})..."
        if "${COMPOSE_CMD[@]}" build --quiet; then
            return 0
        fi
        echo "Build attempt $attempt failed."
        if [ "$attempt" -lt "$BUILD_RETRIES" ]; then
            echo "Retrying build..."
            sleep 3
        fi
    done
    return 1
}

wait_for_hivemind_ready() {
    local try=1
    while [ "$try" -le "$READINESS_RETRIES" ]; do
        if "${COMPOSE_CMD[@]}" exec -T e2e-runner python - <<'PY'
import asyncio
import base64
import json
import os
import time

import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

host = os.getenv("HIVEMIND_HOST", "hivemind")
port = int(os.getenv("HIVEMIND_PORT", "5672"))
name = os.getenv("HIVEMIND_CLIENT_NAME", "test-client")
key = os.getenv("HIVEMIND_CLIENT_KEY", "test-api-key")
crypto_key_raw = os.getenv("HIVEMIND_CLIENT_CRYPTO_KEY", "")
if not crypto_key_raw:
    raise SystemExit(1)

raw = f"{name}:{key}".encode("utf-8")
token = base64.b64encode(raw).decode("utf-8")
url = f"ws://{host}:{port}?authorization={token}"
crypto_key = crypto_key_raw.encode("utf-8")
aesgcm = AESGCM(crypto_key)

def _hex(data: bytes) -> str:
    return data.hex()

def _unhex(data: str) -> bytes:
    return bytes.fromhex(data)

def enc_bus(payload: dict) -> dict:
    nonce = os.urandom(16)
    plaintext = json.dumps(payload).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return {
        "nonce": _hex(nonce),
        "ciphertext": _hex(ciphertext),
    }

def dec_bus(envelope: dict) -> dict | None:
    ciphertext = envelope.get("ciphertext")
    nonce = envelope.get("nonce")
    if not isinstance(ciphertext, str) or not isinstance(nonce, str):
        return None
    plaintext = aesgcm.decrypt(_unhex(nonce), _unhex(ciphertext), None)
    parsed = json.loads(plaintext.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else None

async def main() -> int:
    try:
        async with websockets.connect(url) as ws:
            # HiveMind should emit hello/shake frames immediately on connect.
            saw_hello_or_shake = False
            for _ in range(2):
                frame = await asyncio.wait_for(ws.recv(), timeout=3)
                raw_msg = json.loads(frame)
                parsed = dec_bus(raw_msg) if isinstance(raw_msg, dict) else None
                msg = parsed if isinstance(parsed, dict) else raw_msg
                if isinstance(msg, dict) and msg.get("msg_type") in {"hello", "shake"}:
                    saw_hello_or_shake = True

            if saw_hello_or_shake:
                return 0
    except Exception:
        return 1
    return 1

raise SystemExit(asyncio.run(main()))
PY
        then
            echo "HiveMind readiness probe passed."
            return 0
        fi

        echo "HiveMind readiness probe not ready yet (attempt ${try}/${READINESS_RETRIES})..."
        sleep "$READINESS_INTERVAL"
        try=$((try + 1))
    done
    return 1
}

# ── Build ────────────────────────────────────────────────
if ! build_images; then
    echo "Image build failed after retries."
    exit 1
fi

# ── Start ────────────────────────────────────────────────
echo "Starting all services (messagebus + skill + DB + mock RENERYO + HiveMind)..."
if ! "${COMPOSE_CMD[@]}" up -d; then
    EXIT_CODE=1
    echo "❌ Startup failed before tests"
    collect_logs
    exit "$EXIT_CODE"
fi
STACK_STARTED=true

# Quick health check
echo "Checking service health..."
"${COMPOSE_CMD[@]}" ps --format "table {{.Name}}\t{{.Status}}"
echo ""

echo "Probing HiveMind voice path readiness..."
if ! wait_for_hivemind_ready; then
    EXIT_CODE=1
    echo "❌ HiveMind readiness probe failed"
    collect_logs
    exit "$EXIT_CODE"
fi

# ── Run tests ────────────────────────────────────────────
echo "Running Voice E2E tests..."
set +e
"${COMPOSE_CMD[@]}" exec -T e2e-runner \
    pytest tests/test_e2e/test_hivemind_pipeline.py -v --tb=short -m e2e
EXIT_CODE=$?
set -e

# ── Collect logs on failure ──────────────────────────────
if [ "$EXIT_CODE" -ne 0 ]; then
    collect_logs
fi

# ── Summary ──────────────────────────────────────────────
echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "✅ All voice E2E tests PASSED"
else
    echo "❌ Voice E2E tests FAILED (exit code: $EXIT_CODE)"
fi

exit "$EXIT_CODE"
