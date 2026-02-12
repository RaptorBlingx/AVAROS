"""
Unit tests for E2E helper utilities.

These tests validate ``send_intent_and_wait`` and message construction
in isolation — no Docker services required.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from tests.test_e2e.conftest import (
    _CONNECT_WAIT_S,
    _DEFAULT_TIMEOUT_S,
    send_intent_and_wait,
)

pytestmark = pytest.mark.e2e


# ── Fake Message ────────────────────────────────────────


class FakeMessage:
    """Minimal stand-in for ``ovos_bus_client.Message``."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or {}


# ── Tests ───────────────────────────────────────────────


class TestSendIntentAndWait:
    """Unit tests for the ``send_intent_and_wait`` helper."""

    def test_returns_response_on_immediate_speak(self) -> None:
        """Returns speak data when handler fires immediately."""
        client = MagicMock()
        speak_callback = None

        def _capture_on(event: str, callback: Any) -> None:
            nonlocal speak_callback
            if event == "speak":
                speak_callback = callback

        client.on.side_effect = _capture_on
        client.remove = MagicMock()

        def _emit_side_effect(msg: Any) -> None:
            # Simulate immediate speak response
            if speak_callback:
                speak_callback(FakeMessage({"utterance": "OEE is 85%"}))

        client.emit.side_effect = _emit_side_effect

        result = send_intent_and_wait(client, "kpi.oee.intent", timeout=2)

        assert result is not None
        assert result["utterance"] == "OEE is 85%"

    def test_returns_none_on_timeout(self) -> None:
        """Returns None when no speak event arrives within timeout."""
        client = MagicMock()
        client.on = MagicMock()
        client.remove = MagicMock()
        client.emit = MagicMock()

        result = send_intent_and_wait(client, "kpi.oee.intent", timeout=0.1)

        assert result is None

    def test_passes_data_payload_to_emit(self) -> None:
        """Intent data dict is forwarded in the emitted message."""
        client = MagicMock()
        client.on = MagicMock()
        client.remove = MagicMock()

        emitted = []

        def _capture_emit(msg: Any) -> None:
            emitted.append(msg)

        client.emit.side_effect = _capture_emit

        send_intent_and_wait(
            client,
            "kpi.energy.per_unit.intent",
            data={"asset": "Line-1", "period": "today"},
            timeout=0.1,
        )

        assert len(emitted) == 1
        msg = emitted[0]
        assert msg.data["asset"] == "Line-1"
        assert msg.data["period"] == "today"

    def test_removes_speak_listener_after_response(self) -> None:
        """Speak listener is cleaned up after response to avoid leakage."""
        client = MagicMock()
        registered_callback = None

        def _capture_on(event: str, callback: Any) -> None:
            nonlocal registered_callback
            if event == "speak":
                registered_callback = callback

        client.on.side_effect = _capture_on

        def _emit_fire(msg: Any) -> None:
            if registered_callback:
                registered_callback(FakeMessage({"utterance": "test"}))

        client.emit.side_effect = _emit_fire

        send_intent_and_wait(client, "test.intent", timeout=1)

        client.remove.assert_called_once_with("speak", registered_callback)

    def test_removes_speak_listener_on_timeout(self) -> None:
        """Speak listener is cleaned up even when response times out."""
        client = MagicMock()
        client.on = MagicMock()
        client.remove = MagicMock()
        client.emit = MagicMock()

        send_intent_and_wait(client, "test.intent", timeout=0.1)

        client.remove.assert_called_once()


class TestDefaultConstants:
    """Validate default configuration constants."""

    def test_default_timeout_is_positive(self) -> None:
        """Default timeout must be a positive number."""
        assert _DEFAULT_TIMEOUT_S > 0

    def test_connect_wait_is_reasonable(self) -> None:
        """Connection wait should be between 1 and 30 seconds."""
        assert 1 <= _CONNECT_WAIT_S <= 30
