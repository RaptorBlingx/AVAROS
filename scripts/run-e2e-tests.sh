#!/bin/bash
# =================================================================
# AVAROS E2E Voice Pipeline Tests
#
# Self-contained CI script that:
#   1. Builds all E2E Docker images
#   2. Starts the full stack (messagebus, skill, DB, mock RENERYO)
#   3. Waits for services to become healthy
#   4. Runs pytest inside the e2e-runner container
#   5. Collects logs on failure
#   6. Tears everything down
#
# Usage:
#   ./scripts/run-e2e-tests.sh
# =================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.e2e.yml"
BUILD_RETRIES=2
READINESS_RETRIES=30
READINESS_INTERVAL=2

echo "=== AVAROS E2E Voice Pipeline Tests ==="
echo "Project root: $PROJECT_ROOT"
echo ""

build_images() {
    local attempt
    for attempt in $(seq 1 "$BUILD_RETRIES"); do
        echo "Building Docker images (attempt ${attempt}/${BUILD_RETRIES})..."
        if docker compose -f "$COMPOSE_FILE" build --quiet; then
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

wait_for_voice_ready() {
    local try=1
    while [ "$try" -le "$READINESS_RETRIES" ]; do
        if docker compose -f "$COMPOSE_FILE" exec -T e2e-runner python - <<'PY'
import threading
try:
    from ovos_bus_client import MessageBusClient, Message
except ImportError:
    from mycroft_bus_client import MessageBusClient, Message

client = MessageBusClient(host="ovos_messagebus", port=8181, route="/core")
client.run_in_thread()
event = threading.Event()

def on_speak(msg):
    text = str(msg.data.get("utterance", "")).lower()
    if text.strip():
        event.set()

client.on("speak", on_speak)
try:
    client.emit(
        Message(
            "avaros-manufacturing.avaros:kpi.oee.intent",
            {"asset": "Line-1", "period": "today"},
        )
    )
    ok = event.wait(timeout=4.0)
finally:
    client.remove("speak", on_speak)
    client.close()

raise SystemExit(0 if ok else 1)
PY
        then
            echo "Voice readiness probe passed."
            return 0
        fi

        echo "Voice readiness probe not ready yet (attempt ${try}/${READINESS_RETRIES})..."
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
echo "Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# Quick health check
echo "Checking service health..."
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}"
echo ""

echo "Probing voice pipeline readiness..."
if ! wait_for_voice_ready; then
    echo "Voice readiness probe failed."
    echo ""
    echo "=== avaros-skill logs ==="
    docker compose -f "$COMPOSE_FILE" logs --tail=120 avaros-skill || true
    echo ""
    echo "=== ovos-messagebus logs ==="
    docker compose -f "$COMPOSE_FILE" logs --tail=80 ovos_messagebus || true
    docker compose -f "$COMPOSE_FILE" down -v
    exit 1
fi

# ── Run tests ────────────────────────────────────────────
echo "Running E2E tests..."
docker compose -f "$COMPOSE_FILE" exec -T e2e-runner \
    pytest tests/test_e2e/test_helpers.py tests/test_e2e/test_voice_pipeline.py -v --tb=short --timeout=60 -m e2e

EXIT_CODE=$?

# ── Collect logs on failure ──────────────────────────────
if [ "$EXIT_CODE" -ne 0 ]; then
    echo ""
    echo "=== avaros-skill logs ==="
    docker compose -f "$COMPOSE_FILE" logs --tail=80 avaros-skill
    echo ""
    echo "=== ovos-messagebus logs ==="
    docker compose -f "$COMPOSE_FILE" logs --tail=40 ovos_messagebus
fi

# ── Cleanup ──────────────────────────────────────────────
echo ""
echo "Cleaning up..."
docker compose -f "$COMPOSE_FILE" down -v

# ── Result ───────────────────────────────────────────────
if [ "$EXIT_CODE" -eq 0 ]; then
    echo ""
    echo "=== ALL E2E TESTS PASSED ==="
else
    echo ""
    echo "=== E2E TESTS FAILED (exit code $EXIT_CODE) ==="
fi

exit "$EXIT_CODE"
