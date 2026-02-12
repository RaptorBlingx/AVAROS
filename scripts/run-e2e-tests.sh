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
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.e2e.yml"
STARTUP_WAIT=20  # seconds to wait for skill registration

echo "=== AVAROS E2E Voice Pipeline Tests ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# ── Build ────────────────────────────────────────────────
echo "Building Docker images..."
docker compose -f "$COMPOSE_FILE" build --quiet

# ── Start ────────────────────────────────────────────────
echo "Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# ── Wait for readiness ────────────────────────────────────
echo "Waiting ${STARTUP_WAIT}s for services to initialise..."
sleep "$STARTUP_WAIT"

# Quick health check
echo "Checking service health..."
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}"
echo ""

# ── Run tests ────────────────────────────────────────────
echo "Running E2E tests..."
docker compose -f "$COMPOSE_FILE" exec -T e2e-runner \
    pytest tests/test_e2e/ -v --tb=short --timeout=60 -m e2e

EXIT_CODE=$?

# ── Collect logs on failure ──────────────────────────────
if [ "$EXIT_CODE" -ne 0 ]; then
    echo ""
    echo "=== avaros-skill logs ==="
    docker compose -f "$COMPOSE_FILE" logs --tail=80 avaros-skill
    echo ""
    echo "=== ovos-messagebus logs ==="
    docker compose -f "$COMPOSE_FILE" logs --tail=40 ovos-messagebus
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
