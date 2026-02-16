"""
E2E Voice Pipeline — Shared fixtures and helpers.

Provides a session-scoped MessageBusClient that connects to the
OVOS message bus and a ``send_intent_and_wait`` helper used by all
E2E test modules.

Tests in this package are marked with ``@pytest.mark.e2e`` so they are
excluded from regular ``pytest tests/ -v`` runs. Run them with:
``pytest tests/test_e2e/ -v -m e2e``.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import pytest

try:
    from ovos_bus_client import Message, MessageBusClient
except ImportError:
    from mycroft_bus_client import Message, MessageBusClient  # type: ignore[no-redef]


# ── Constants ───────────────────────────────────────────

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 8181
_CONNECT_WAIT_S = 5
_DEFAULT_TIMEOUT_S = 15
_SKILL_ID = "avaros-manufacturing.avaros"


# ── Helper ──────────────────────────────────────────────


def send_intent_and_wait(
    client: MessageBusClient,
    intent_name: str,
    data: dict[str, Any] | None = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> dict[str, Any] | None:
    """Send an intent message and wait for the ``speak`` response.

    Args:
        client: Connected OVOS ``MessageBusClient``.
        intent_name: Full intent message type (e.g. ``kpi.oee.intent``).
        data: Optional data payload (asset, period, …).
        timeout: Maximum seconds to wait for a response.

    Returns:
        The ``speak`` message ``data`` dict, or ``None`` on timeout.
    """
    response: list[dict[str, Any]] = []
    event = threading.Event()
    full_intent_name = f"{_SKILL_ID}:{intent_name}"

    def _on_speak(msg: Message) -> None:
        response.append(msg.data)
        event.set()

    client.on("speak", _on_speak)
    try:
        client.emit(Message(full_intent_name, data or {}))
        event.wait(timeout=timeout)
    finally:
        # Remove subscriber to avoid cross-test leakage
        client.remove("speak", _on_speak)

    return response[0] if response else None


# ── Session-Scoped Fixtures ─────────────────────────────


@pytest.fixture(scope="session")
def bus_client() -> MessageBusClient:
    """Connect to the OVOS message bus for the entire test session.

    Yields:
        A connected ``MessageBusClient``.
    """
    host = os.environ.get("MESSAGEBUS_HOST", _DEFAULT_HOST)
    port = int(os.environ.get("MESSAGEBUS_PORT", str(_DEFAULT_PORT)))

    client = MessageBusClient(host=host, port=port, route="/core")
    client.run_in_thread()

    # Wait for the skill to register its intents on the bus.
    time.sleep(_CONNECT_WAIT_S)

    yield client

    client.close()
