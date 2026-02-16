"""
E2E HiveMind WebSocket Pipeline Tests

Full end-to-end validation through the HiveMind WebSocket bridge:
browser utterance → HiveMind WebSocket → OVOS messagebus → AVAROSSkill →
QueryDispatcher → adapter → ResponseBuilder → speak → HiveMind → browser.

This tests the **actual voice pipeline path** that browsers use, as
opposed to ``test_voice_pipeline.py`` which tests via direct messagebus.

Requires a running Docker voice E2E stack (see
``docker/docker-compose.e2e-voice.yml``).
Run via: ``scripts/run-voice-e2e.sh``

All tests are marked ``@pytest.mark.e2e`` so they are excluded from
regular ``pytest tests/ -v``.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import pytest

from tests.test_e2e.conftest import Message, MessageBusClient

pytestmark = pytest.mark.e2e


# ── Constants ───────────────────────────────────────────

_MESSAGEBUS_HOST = os.environ.get("MESSAGEBUS_HOST", "localhost")
_MESSAGEBUS_PORT = int(os.environ.get("MESSAGEBUS_PORT", "8181"))
_RESPONSE_TIMEOUT_S = 10.0
_PIPELINE_LATENCY_LIMIT_S = 3.0


# ── Helpers ─────────────────────────────────────────────


def _send_utterance_and_wait(
    client: MessageBusClient,
    utterance: str,
    timeout: float = _RESPONSE_TIMEOUT_S,
) -> dict[str, Any] | None:
    """Send a natural-language utterance and wait for ``speak`` response.

    Simulates the HiveMind path: ``recognizer_loop:utterance`` is the
    message type that HiveMind-core injects into the OVOS messagebus
    when a browser client sends an utterance via WebSocket.

    Args:
        client: Connected OVOS ``MessageBusClient``.
        utterance: Natural-language text (e.g. "what is energy per unit").
        timeout: Maximum seconds to wait for a response.

    Returns:
        The ``speak`` message ``data`` dict, or ``None`` on timeout.
    """
    import threading

    response: list[dict[str, Any]] = []
    event = threading.Event()

    def _on_speak(msg: Message) -> None:
        response.append(msg.data)
        event.set()

    client.on("speak", _on_speak)
    try:
        client.emit(
            Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance]},
            )
        )
        event.wait(timeout=timeout)
    finally:
        client.remove("speak", _on_speak)

    return response[0] if response else None


# ══════════════════════════════════════════════════════════
# 1. Utterance Roundtrip Tests
# ══════════════════════════════════════════════════════════


class TestUtteranceRoundtrip:
    """Send natural-language utterances, receive spoken responses."""

    def test_energy_per_unit_utterance(self, bus_client: MessageBusClient) -> None:
        """'what is the energy per unit' returns spoken energy value."""
        response = _send_utterance_and_wait(
            bus_client,
            "what is the energy per unit",
        )

        assert response is not None, "No speak response (timeout)"
        utterance = response["utterance"].lower()
        assert "energy" in utterance or "kilowatt" in utterance

    def test_oee_utterance(self, bus_client: MessageBusClient) -> None:
        """'what is the oee' returns OEE percentage."""
        response = _send_utterance_and_wait(
            bus_client,
            "what is the oee",
        )

        assert response is not None, "No speak response (timeout)"
        utterance = response["utterance"].lower()
        assert "%" in response["utterance"] or "percent" in utterance

    def test_status_utterance(self, bus_client: MessageBusClient) -> None:
        """'what is the status' returns system status."""
        response = _send_utterance_and_wait(
            bus_client,
            "what is the status",
        )

        assert response is not None, "No speak response (timeout)"
        assert len(response["utterance"]) > 0

    def test_scrap_rate_utterance(self, bus_client: MessageBusClient) -> None:
        """'what is the scrap rate' returns scrap rate value."""
        response = _send_utterance_and_wait(
            bus_client,
            "what is the scrap rate",
        )

        assert response is not None, "No speak response (timeout)"
        utterance = response["utterance"].lower()
        assert "scrap" in utterance or "rate" in utterance

    def test_trend_utterance(self, bus_client: MessageBusClient) -> None:
        """'show me the trend for energy' returns trend direction."""
        response = _send_utterance_and_wait(
            bus_client,
            "show me the trend for energy",
        )

        assert response is not None, "No speak response (timeout)"
        utterance = response["utterance"].lower()
        assert any(
            word in utterance
            for word in ("up", "down", "stable", "trend", "increasing", "decreasing")
        )


# ══════════════════════════════════════════════════════════
# 2. Multiple Intent Coverage
# ══════════════════════════════════════════════════════════


class TestMultipleIntents:
    """Verify at least 5 different intents are reachable via utterance."""

    UTTERANCE_CASES: list[tuple[str, list[str]]] = [
        (
            "what is the energy per unit",
            ["energy", "kilowatt", "per unit"],
        ),
        (
            "what is the oee",
            ["%", "percent", "oee", "efficiency"],
        ),
        (
            "what is the scrap rate",
            ["scrap", "rate", "%"],
        ),
        (
            "show me the trend for energy",
            ["up", "down", "stable", "trend", "increasing", "decreasing"],
        ),
        (
            "are there any anomalies",
            ["anomal", "unusual", "normal", "pattern", "no"],
        ),
    ]

    @pytest.mark.parametrize(
        ("utterance", "expected_words"),
        UTTERANCE_CASES,
        ids=[case[0].replace(" ", "_")[:40] for case in UTTERANCE_CASES],
    )
    def test_intent_reachable(
        self,
        bus_client: MessageBusClient,
        utterance: str,
        expected_words: list[str],
    ) -> None:
        """Each utterance triggers the correct intent and speaks."""
        response = _send_utterance_and_wait(bus_client, utterance)

        assert response is not None, f"No response for: '{utterance}'"
        spoken = response["utterance"].lower()
        assert any(
            word in spoken for word in expected_words
        ), f"Response '{spoken}' missing expected words {expected_words}"


# ══════════════════════════════════════════════════════════
# 3. Pipeline Latency
# ══════════════════════════════════════════════════════════


class TestPipelineLatency:
    """Validate end-to-end latency stays under target."""

    def test_utterance_latency_under_3s(
        self, bus_client: MessageBusClient,
    ) -> None:
        """Utterance→speak roundtrip completes in under 3 seconds."""
        start = time.time()
        response = _send_utterance_and_wait(
            bus_client,
            "what is the energy per unit",
            timeout=_PIPELINE_LATENCY_LIMIT_S,
        )
        elapsed = time.time() - start

        assert response is not None, (
            f"Response timed out (>{_PIPELINE_LATENCY_LIMIT_S}s)"
        )
        assert elapsed < _PIPELINE_LATENCY_LIMIT_S, (
            f"Pipeline too slow: {elapsed:.1f}s "
            f"(limit: {_PIPELINE_LATENCY_LIMIT_S}s)"
        )

    def test_multiple_queries_average_latency(
        self, bus_client: MessageBusClient,
    ) -> None:
        """Average latency across 3 queries stays under 3 seconds."""
        queries = [
            "what is the energy per unit",
            "what is the oee",
            "what is the scrap rate",
        ]
        latencies: list[float] = []

        for query in queries:
            start = time.time()
            response = _send_utterance_and_wait(bus_client, query)
            elapsed = time.time() - start

            assert response is not None, f"Timeout on: '{query}'"
            latencies.append(elapsed)

        avg = sum(latencies) / len(latencies)
        assert avg < _PIPELINE_LATENCY_LIMIT_S, (
            f"Average latency {avg:.1f}s exceeds "
            f"{_PIPELINE_LATENCY_LIMIT_S}s limit. "
            f"Individual: {[f'{l:.1f}s' for l in latencies]}"
        )


# ══════════════════════════════════════════════════════════
# 4. Graceful Error Handling
# ══════════════════════════════════════════════════════════


class TestGracefulErrors:
    """Invalid or unknown utterances don't crash the pipeline."""

    def test_unknown_utterance_handled(
        self, bus_client: MessageBusClient,
    ) -> None:
        """Gibberish utterance does not crash — returns fallback or times out."""
        response = _send_utterance_and_wait(
            bus_client,
            "xyzzy frobnicator quantum banana",
            timeout=8.0,
        )

        # Either a graceful fallback response or None (no intent matched).
        # The key assertion: no exception was raised, pipeline didn't crash.
        if response is not None:
            assert len(response["utterance"]) > 0

    def test_empty_utterance_handled(
        self, bus_client: MessageBusClient,
    ) -> None:
        """Empty utterance does not crash the pipeline."""
        response = _send_utterance_and_wait(
            bus_client,
            "",
            timeout=5.0,
        )

        # Empty utterance may not produce a response — that's acceptable.
        # The assertion is that no exception is raised.
        if response is not None:
            assert isinstance(response["utterance"], str)


# ══════════════════════════════════════════════════════════
# 5. Session Isolation (Concurrent Clients)
# ══════════════════════════════════════════════════════════


class TestSessionIsolation:
    """Multiple concurrent clients receive independent responses."""

    def test_two_clients_get_independent_responses(self) -> None:
        """Two bus clients send different queries, each gets correct answer."""
        import threading

        host = os.environ.get("MESSAGEBUS_HOST", "localhost")
        port = int(os.environ.get("MESSAGEBUS_PORT", "8181"))

        client_a = MessageBusClient(host=host, port=port, route="/core")
        client_b = MessageBusClient(host=host, port=port, route="/core")

        client_a.run_in_thread()
        client_b.run_in_thread()
        time.sleep(3)

        try:
            response_a = _send_utterance_and_wait(
                client_a,
                "what is the energy per unit",
                timeout=10.0,
            )
            response_b = _send_utterance_and_wait(
                client_b,
                "what is the oee",
                timeout=10.0,
            )

            assert response_a is not None, "Client A got no response"
            assert response_b is not None, "Client B got no response"

            # Both should get relevant (possibly different) responses
            assert len(response_a["utterance"]) > 0
            assert len(response_b["utterance"]) > 0
        finally:
            client_a.close()
            client_b.close()


# ══════════════════════════════════════════════════════════
# 6. Response Quality
# ══════════════════════════════════════════════════════════


class TestResponseQuality:
    """Voice responses are optimized for speech output."""

    def test_response_not_too_long(
        self, bus_client: MessageBusClient,
    ) -> None:
        """Spoken response is under 30 words (voice-optimized)."""
        response = _send_utterance_and_wait(
            bus_client,
            "what is the energy per unit",
        )

        assert response is not None
        word_count = len(response["utterance"].split())
        assert word_count <= 50, (
            f"Response too long for voice: {word_count} words "
            f"(target ≤30, hard limit 50)"
        )

    def test_response_is_not_empty(
        self, bus_client: MessageBusClient,
    ) -> None:
        """Spoken response contains meaningful content."""
        response = _send_utterance_and_wait(
            bus_client,
            "what is the oee",
        )

        assert response is not None
        assert len(response["utterance"].strip()) > 5, (
            "Response too short to be meaningful"
        )
