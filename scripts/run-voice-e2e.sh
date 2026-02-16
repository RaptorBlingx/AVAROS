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
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_COMPOSE="$PROJECT_ROOT/docker/docker-compose.e2e.yml"
VOICE_COMPOSE="$PROJECT_ROOT/docker/docker-compose.e2e-voice.yml"
STARTUP_WAIT=20  # seconds to wait for skill + HiveMind registration
KEEP_CONTAINERS=false

if [[ "${1:-}" == "--keep" ]]; then
    KEEP_CONTAINERS=true
fi

COMPOSE_CMD="docker compose -f $BASE_COMPOSE -f $VOICE_COMPOSE"

echo "=== AVAROS Voice E2E Pipeline Tests ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# ── Cleanup function ─────────────────────────────────────
cleanup() {
    if [[ "$KEEP_CONTAINERS" == "false" ]]; then
        echo ""
        echo "Tearing down containers..."
        $COMPOSE_CMD down -v --remove-orphans 2>/dev/null || true
    else
        echo ""
        echo "Keeping containers running (--keep flag)."
        echo "Tear down manually: $COMPOSE_CMD down -v"
    fi
}
trap cleanup EXIT

# ── Build ────────────────────────────────────────────────
echo "Building Docker images..."
$COMPOSE_CMD build --quiet

# ── Start ────────────────────────────────────────────────
echo "Starting all services (messagebus + skill + DB + mock RENERYO + HiveMind)..."
$COMPOSE_CMD up -d

# ── Wait for readiness ───────────────────────────────────
echo "Waiting ${STARTUP_WAIT}s for services to initialise..."
sleep "$STARTUP_WAIT"

# Quick health check
echo "Checking service health..."
$COMPOSE_CMD ps --format "table {{.Name}}\t{{.Status}}"
echo ""

# ── Run tests ────────────────────────────────────────────
echo "Running Voice E2E tests..."
$COMPOSE_CMD exec -T e2e-runner \
    pytest tests/test_e2e/ -v --tb=short --timeout=60 -m e2e

EXIT_CODE=$?

# ── Collect logs on failure ──────────────────────────────
if [ "$EXIT_CODE" -ne 0 ]; then
    echo ""
    echo "=== avaros-skill logs ==="
    $COMPOSE_CMD logs --tail=80 avaros-skill
    echo ""
    echo "=== ovos-messagebus logs ==="
    $COMPOSE_CMD logs --tail=40 ovos_messagebus
    echo ""
    echo "=== hivemind logs ==="
    $COMPOSE_CMD logs --tail=40 hivemind
fi

# ── Summary ──────────────────────────────────────────────
echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "✅ All voice E2E tests PASSED"
else
    echo "❌ Voice E2E tests FAILED (exit code: $EXIT_CODE)"
fi

exit "$EXIT_CODE"
