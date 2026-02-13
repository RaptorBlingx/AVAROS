"""Integration tests for HiveMind-core Docker deployment.

These tests verify the HiveMind container infrastructure and connectivity.
They require Docker to be running with the AVAROS stack.

Mark: @pytest.mark.integration — skipped unless Docker stack is running.

Tests:
    - Container service definition is valid
    - WebSocket port is accessible (when running)
    - Nginx proxy configuration includes hivemind upstream
    - Session isolation (two concurrent connections)
"""

import json
import os
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCKER_DIR = PROJECT_ROOT / "docker"
COMPOSE_FILE = DOCKER_DIR / "docker-compose.avaros.yml"
STANDALONE_COMPOSE = PROJECT_ROOT / "docker-compose.yml"
NGINX_CONF = DOCKER_DIR / "nginx" / "nginx.conf"
NGINX_PROD_CONF = DOCKER_DIR / "nginx" / "nginx-production.conf"
HIVEMIND_DOCKERFILE = DOCKER_DIR / "hivemind" / "Dockerfile"
HIVEMIND_ENTRYPOINT = DOCKER_DIR / "hivemind" / "entrypoint.sh"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

# Default HiveMind port
HIVEMIND_PORT = int(os.environ.get("HIVEMIND_PORT", "5678"))


# ===================================================================
# File-based tests (always runnable — no Docker required)
# ===================================================================


class TestHiveMindDockerFiles:
    """Verify HiveMind Docker files exist and have correct content."""

    def test_dockerfile_exists(self) -> None:
        """HiveMind Dockerfile exists in docker/hivemind/."""
        assert HIVEMIND_DOCKERFILE.is_file(), (
            f"Missing {HIVEMIND_DOCKERFILE}"
        )

    def test_entrypoint_exists(self) -> None:
        """HiveMind entrypoint.sh exists and is not empty."""
        assert HIVEMIND_ENTRYPOINT.is_file(), (
            f"Missing {HIVEMIND_ENTRYPOINT}"
        )
        content = HIVEMIND_ENTRYPOINT.read_text()
        assert len(content) > 100, "entrypoint.sh appears empty"

    def test_entrypoint_is_executable_script(self) -> None:
        """Entrypoint starts with bash shebang."""
        content = HIVEMIND_ENTRYPOINT.read_text()
        assert content.startswith("#!/bin/bash"), (
            "entrypoint.sh must start with #!/bin/bash"
        )

    def test_dockerfile_installs_hivemind_core(self) -> None:
        """Dockerfile installs the hivemind-core package."""
        content = HIVEMIND_DOCKERFILE.read_text()
        assert "hivemind-core" in content, (
            "Dockerfile must install hivemind-core"
        )

    def test_dockerfile_exposes_port_5678(self) -> None:
        """Dockerfile exposes the WebSocket port."""
        content = HIVEMIND_DOCKERFILE.read_text()
        assert "EXPOSE 5678" in content, (
            "Dockerfile must EXPOSE 5678"
        )


class TestComposeHiveMindService:
    """Verify hivemind service is defined in Docker Compose files."""

    def test_avaros_compose_has_hivemind_service(self) -> None:
        """docker-compose.avaros.yml defines a hivemind service."""
        content = COMPOSE_FILE.read_text()
        assert "hivemind:" in content, (
            "docker-compose.avaros.yml must define hivemind service"
        )

    def test_avaros_compose_hivemind_port_mapping(self) -> None:
        """Compose maps port 5678 for HiveMind WebSocket."""
        content = COMPOSE_FILE.read_text()
        assert "5678" in content, (
            "docker-compose.avaros.yml must map port 5678"
        )

    def test_avaros_compose_hivemind_volume(self) -> None:
        """Compose defines hivemind_data volume."""
        content = COMPOSE_FILE.read_text()
        assert "hivemind_data" in content, (
            "docker-compose.avaros.yml must define hivemind_data volume"
        )

    def test_avaros_compose_hivemind_ovos_bus_host(self) -> None:
        """Compose sets OVOS_BUS_HOST to ovos_core."""
        content = COMPOSE_FILE.read_text()
        assert "OVOS_BUS_HOST=ovos_core" in content, (
            "hivemind service must set OVOS_BUS_HOST=ovos_core"
        )

    def test_standalone_compose_has_hivemind(self) -> None:
        """Standalone docker-compose.yml defines hivemind service."""
        content = STANDALONE_COMPOSE.read_text()
        assert "hivemind:" in content, (
            "docker-compose.yml must define hivemind service"
        )

    def test_standalone_compose_hivemind_volume(self) -> None:
        """Standalone compose defines hivemind-data volume."""
        content = STANDALONE_COMPOSE.read_text()
        assert "hivemind-data" in content, (
            "docker-compose.yml must define hivemind-data volume"
        )


class TestNginxHiveMindProxy:
    """Verify Nginx configs include HiveMind WebSocket proxy."""

    def test_nginx_conf_has_hivemind_upstream(self) -> None:
        """nginx.conf defines hivemind_ws upstream."""
        content = NGINX_CONF.read_text()
        assert "hivemind_ws" in content, (
            "nginx.conf must define hivemind_ws upstream"
        )

    def test_nginx_conf_has_hivemind_location(self) -> None:
        """nginx.conf proxies /hivemind to hivemind_ws."""
        content = NGINX_CONF.read_text()
        assert "location /hivemind" in content, (
            "nginx.conf must have location /hivemind block"
        )

    def test_nginx_conf_websocket_upgrade(self) -> None:
        """nginx.conf sets WebSocket upgrade headers for /hivemind."""
        content = NGINX_CONF.read_text()
        # Find the hivemind section specifically
        hivemind_idx = content.find("location /hivemind")
        assert hivemind_idx > -1
        hivemind_block = content[hivemind_idx:hivemind_idx + 500]
        assert "proxy_http_version 1.1" in hivemind_block
        assert 'Connection "upgrade"' in hivemind_block

    def test_nginx_conf_long_timeout(self) -> None:
        """nginx.conf has long read timeout for persistent WebSocket."""
        content = NGINX_CONF.read_text()
        hivemind_idx = content.find("location /hivemind")
        hivemind_block = content[hivemind_idx:hivemind_idx + 500]
        assert "86400" in hivemind_block, (
            "HiveMind proxy needs 24h timeout for persistent WebSocket"
        )

    def test_production_nginx_has_hivemind(self) -> None:
        """nginx-production.conf also defines HiveMind proxy."""
        content = NGINX_PROD_CONF.read_text()
        assert "hivemind_ws" in content, (
            "nginx-production.conf must define hivemind_ws upstream"
        )
        assert "location /hivemind" in content, (
            "nginx-production.conf must have location /hivemind"
        )


class TestEnvExample:
    """Verify .env.example documents HiveMind configuration."""

    def test_env_example_has_hivemind_port(self) -> None:
        """.env.example documents HIVEMIND_PORT."""
        content = ENV_EXAMPLE.read_text()
        assert "HIVEMIND_PORT" in content

    def test_env_example_has_hivemind_client_name(self) -> None:
        """.env.example documents HIVEMIND_CLIENT_NAME."""
        content = ENV_EXAMPLE.read_text()
        assert "HIVEMIND_CLIENT_NAME" in content

    def test_env_example_has_hivemind_access_key(self) -> None:
        """.env.example documents HIVEMIND_ACCESS_KEY."""
        content = ENV_EXAMPLE.read_text()
        assert "HIVEMIND_ACCESS_KEY" in content

    def test_env_example_has_hivemind_password(self) -> None:
        """.env.example documents HIVEMIND_PASSWORD."""
        content = ENV_EXAMPLE.read_text()
        assert "HIVEMIND_PASSWORD" in content

    def test_env_example_references_dec_026(self) -> None:
        """.env.example references DEC-026 decision."""
        content = ENV_EXAMPLE.read_text()
        assert "DEC-026" in content


# ===================================================================
# Infrastructure tests (require Docker stack running)
# ===================================================================


def _hivemind_port_open() -> bool:
    """Check if HiveMind port is reachable on localhost."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(("localhost", HIVEMIND_PORT))
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


hivemind_running = pytest.mark.skipif(
    not _hivemind_port_open(),
    reason=f"HiveMind not running on localhost:{HIVEMIND_PORT}",
)


@pytest.mark.integration
class TestHiveMindConnectivity:
    """Tests that require the HiveMind Docker container to be running."""

    @hivemind_running
    def test_hivemind_container_starts(self) -> None:
        """HiveMind container is healthy — port 5678 is open."""
        assert _hivemind_port_open(), (
            "HiveMind port 5678 is not reachable"
        )

    @hivemind_running
    def test_websocket_connection(self) -> None:
        """Can establish WebSocket connection to HiveMind."""
        import asyncio

        async def _connect() -> bool:
            try:
                import websockets

                async with websockets.connect(
                    f"ws://localhost:{HIVEMIND_PORT}",
                    open_timeout=5,
                ) as ws:
                    return ws.open
            except Exception:
                return False

        result = asyncio.run(_connect())
        assert result, "WebSocket connection to HiveMind failed"

    @hivemind_running
    def test_websocket_receives_handshake(self) -> None:
        """HiveMind sends handshake message after WebSocket connect."""
        import asyncio

        async def _receive_handshake() -> dict:
            import websockets

            async with websockets.connect(
                f"ws://localhost:{HIVEMIND_PORT}",
                open_timeout=5,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                return json.loads(raw)

        msg = asyncio.run(_receive_handshake())
        assert isinstance(msg, dict), "Handshake must be valid JSON"

    @hivemind_running
    def test_session_isolation_two_clients(self) -> None:
        """Two concurrent WebSocket clients get independent connections."""
        import asyncio

        async def _dual_connect() -> tuple:
            import websockets

            async with websockets.connect(
                f"ws://localhost:{HIVEMIND_PORT}",
                open_timeout=5,
            ) as ws1:
                async with websockets.connect(
                    f"ws://localhost:{HIVEMIND_PORT}",
                    open_timeout=5,
                ) as ws2:
                    return ws1.open, ws2.open

        ok1, ok2 = asyncio.run(_dual_connect())
        assert ok1 and ok2, "Both clients should connect independently"


class TestNoPortConflicts:
    """Ensure HiveMind port doesn't conflict with existing services."""

    def _ports_in_compose(self, filepath: Path) -> list:
        """Extract host port mappings from a compose file."""
        content = filepath.read_text()
        import re

        # Match patterns like "8080:8080", "${VAR:-8080}:8080"
        return re.findall(r'(\d+):\d+"?\s*$', content, re.MULTILINE)

    def test_port_5678_unique_in_avaros_compose(self) -> None:
        """Port 5678 is only used by HiveMind in avaros compose."""
        content = COMPOSE_FILE.read_text()
        # Count occurrences of 5678 in port mappings (not env vars)
        import re

        port_mappings = re.findall(r'"?\$?\{?[^}]*5678[^"]*:\s*5678', content)
        assert len(port_mappings) == 1, (
            f"Port 5678 should appear exactly once in port mappings, "
            f"found {len(port_mappings)}"
        )
