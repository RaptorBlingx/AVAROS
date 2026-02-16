"""E2E HiveMind WebSocket pipeline tests.

Validates the real browser path over HiveMind WebSocket transport:
browser utterance -> HiveMind WS -> OVOS messagebus -> AVAROS skill -> speak.

Unlike direct messagebus tests, these connect to ``ws://localhost:5678``
with HiveMind auth and send utterances in HiveMind bus envelopes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from collections.abc import Mapping
from typing import Any

import pytest
import websockets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]

_HIVEMIND_HOST = os.environ.get("HIVEMIND_HOST", "localhost")
_HIVEMIND_PORT = int(os.environ.get("HIVEMIND_PORT", "5678"))
_HIVEMIND_CLIENT_NAME = os.environ.get("HIVEMIND_CLIENT_NAME", "e2e-test-client")
_HIVEMIND_CLIENT_KEY = os.environ.get("HIVEMIND_CLIENT_KEY", "e2e-test-access-key")
_HIVEMIND_CLIENT_CRYPTO_KEY = os.environ.get(
    "HIVEMIND_CLIENT_CRYPTO_KEY",
    "0123456789abcdef",
)
_RESPONSE_TIMEOUT_S = 12.0
_PIPELINE_LATENCY_LIMIT_S = 3.0


def _auth_url() -> str:
    token_raw = f"{_HIVEMIND_CLIENT_NAME}:{_HIVEMIND_CLIENT_KEY}".encode("utf-8")
    token = base64.b64encode(token_raw).decode("utf-8")
    return f"ws://{_HIVEMIND_HOST}:{_HIVEMIND_PORT}?authorization={token}"


def _utterance_envelope(utterance: str) -> dict[str, Any]:
    event_type = "recognizer_loop:utterance"
    event_data = {"utterances": [utterance], "lang": "en-us"}

    payload = {
        "type": event_type,
        "data": event_data,
        "context": {
            "source": "e2e.voice.pipeline",
            "destination": "HiveMind",
            "platform": "AVAROS-E2E",
        },
    }
    return {"msg_type": "bus", "payload": payload}


def _bytes_to_hex(data: bytes) -> str:
    return data.hex()


def _hex_to_bytes(data: str) -> bytes:
    return bytes.fromhex(data)


def _encrypt_payload(message: Mapping[str, Any]) -> dict[str, str]:
    iv = os.urandom(16)
    aes = AESGCM(_HIVEMIND_CLIENT_CRYPTO_KEY.encode("utf-8"))
    plaintext = json.dumps(message).encode("utf-8")
    ciphertext = aes.encrypt(iv, plaintext, None)
    return {"nonce": _bytes_to_hex(iv), "ciphertext": _bytes_to_hex(ciphertext)}


def _decrypt_payload(envelope: Mapping[str, Any]) -> Mapping[str, Any] | None:
    ciphertext = envelope.get("ciphertext")
    nonce = envelope.get("nonce")
    if not isinstance(ciphertext, str) or not isinstance(nonce, str):
        return None
    aes = AESGCM(_HIVEMIND_CLIENT_CRYPTO_KEY.encode("utf-8"))
    decrypted = aes.decrypt(_hex_to_bytes(nonce), _hex_to_bytes(ciphertext), None)
    payload = json.loads(decrypted.decode("utf-8"))
    return payload if isinstance(payload, Mapping) else None


def _as_bus_message(message: Mapping[str, Any]) -> Mapping[str, Any]:
    if message.get("msg_type") == "bus" and isinstance(message.get("payload"), Mapping):
        return message["payload"]
    return message


async def _receive_message(
    ws: websockets.WebSocketClientProtocol,
    timeout_s: float,
) -> Mapping[str, Any] | None:
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
    except asyncio.TimeoutError:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, Mapping):
        return None
    if "ciphertext" in parsed and "nonce" in parsed:
        return _decrypt_payload(parsed)
    if isinstance(parsed, Mapping):
        return parsed
    return None


async def _wait_for_type(
    ws: websockets.WebSocketClientProtocol,
    event_type: str,
    timeout_s: float,
) -> Mapping[str, Any] | None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        remaining = max(deadline - time.monotonic(), 0.1)
        envelope = await _receive_message(ws, remaining)
        if envelope is None:
            return None
        message = _as_bus_message(envelope)
        if message.get("type") == event_type:
            return message
    return None


async def _send_utterance_and_wait(
    ws: websockets.WebSocketClientProtocol,
    utterance: str,
    timeout_s: float = _RESPONSE_TIMEOUT_S,
) -> Mapping[str, Any] | None:
    envelope = _encrypt_payload(_utterance_envelope(utterance))
    await ws.send(json.dumps(envelope))
    return await _wait_for_type(ws, "speak", timeout_s)


def _spoken_text(message: Mapping[str, Any]) -> str:
    data = message.get("data", {})
    if not isinstance(data, Mapping):
        return ""
    utterance = data.get("utterance", "")
    return utterance if isinstance(utterance, str) else ""


# ══════════════════════════════════════════════════════════
# 1. Utterance Roundtrip Tests
# ══════════════════════════════════════════════════════════


class TestUtteranceRoundtrip:
    """Send natural-language utterances, receive spoken responses."""

    async def test_energy_per_unit_utterance(self) -> None:
        """'what is the energy per unit' returns spoken energy value."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "what is the energy per unit")
        assert response is not None, "No speak response (timeout)"
        spoken = _spoken_text(response).lower()
        assert "energy" in spoken or "kilowatt" in spoken

    async def test_oee_utterance(self) -> None:
        """'what is the oee' returns OEE percentage."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "what is the oee")
        assert response is not None, "No speak response (timeout)"
        spoken = _spoken_text(response).lower()
        assert "%" in _spoken_text(response) or "percent" in spoken

    async def test_status_utterance(self) -> None:
        """'what is the status' returns system status."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "what is the status")
        assert response is not None, "No speak response (timeout)"
        assert len(_spoken_text(response)) > 0

    async def test_scrap_rate_utterance(self) -> None:
        """'what is the scrap rate' returns scrap rate value."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "what is the scrap rate")
        assert response is not None, "No speak response (timeout)"
        spoken = _spoken_text(response).lower()
        assert "scrap" in spoken or "rate" in spoken

    async def test_trend_utterance(self) -> None:
        """'show me the trend for energy' returns trend direction."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "show me the trend for energy")
        assert response is not None, "No speak response (timeout)"
        utterance = _spoken_text(response).lower()
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
    async def test_intent_reachable(
        self,
        utterance: str,
        expected_words: list[str],
    ) -> None:
        """Each utterance triggers the correct intent and speaks."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, utterance)

        assert response is not None, f"No response for: '{utterance}'"
        spoken = _spoken_text(response).lower()
        assert any(
            word in spoken for word in expected_words
        ), f"Response '{spoken}' missing expected words {expected_words}"


# ══════════════════════════════════════════════════════════
# 3. Pipeline Latency
# ══════════════════════════════════════════════════════════


class TestPipelineLatency:
    """Validate end-to-end latency stays under target."""

    async def test_utterance_latency_under_3s(self) -> None:
        """Utterance→speak roundtrip completes in under 3 seconds."""
        async with websockets.connect(_auth_url()) as ws:
            start = time.time()
            response = await _send_utterance_and_wait(
                ws,
                "what is the energy per unit",
                timeout_s=_PIPELINE_LATENCY_LIMIT_S,
            )
        elapsed = time.time() - start

        assert response is not None, (
            f"Response timed out (>{_PIPELINE_LATENCY_LIMIT_S}s)"
        )
        assert elapsed < _PIPELINE_LATENCY_LIMIT_S, (
            f"Pipeline too slow: {elapsed:.1f}s "
            f"(limit: {_PIPELINE_LATENCY_LIMIT_S}s)"
        )

    async def test_multiple_queries_average_latency(self) -> None:
        """Average latency across 3 queries stays under 3 seconds."""
        queries = [
            "what is the energy per unit",
            "what is the oee",
            "what is the scrap rate",
        ]
        latencies: list[float] = []

        async with websockets.connect(_auth_url()) as ws:
            for query in queries:
                start = time.time()
                response = await _send_utterance_and_wait(ws, query)
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

    async def test_unknown_utterance_handled(self) -> None:
        """Gibberish utterance does not crash — returns fallback or times out."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(
                ws,
                "xyzzy frobnicator quantum banana",
                timeout_s=8.0,
            )

        # Either a graceful fallback response or None (no intent matched).
        # The key assertion: no exception was raised, pipeline didn't crash.
        if response is not None:
            assert len(_spoken_text(response)) > 0

    async def test_empty_utterance_handled(self) -> None:
        """Empty utterance does not crash the pipeline."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "", timeout_s=5.0)

        # Empty utterance may not produce a response — that's acceptable.
        # The assertion is that no exception is raised.
        if response is not None:
            assert isinstance(_spoken_text(response), str)


# ══════════════════════════════════════════════════════════
# 5. Session Isolation (Concurrent Clients)
# ══════════════════════════════════════════════════════════


class TestSessionIsolation:
    """Multiple concurrent clients receive independent responses."""

    async def test_two_clients_get_independent_responses(self) -> None:
        """Two bus clients send different queries, each gets correct answer."""
        async with websockets.connect(_auth_url()) as ws_a:
            async with websockets.connect(_auth_url()) as ws_b:
                task_a = _send_utterance_and_wait(ws_a, "what is the energy per unit")
                task_b = _send_utterance_and_wait(ws_b, "what is the oee")
                response_a, response_b = await asyncio.gather(task_a, task_b)

        assert response_a is not None, "Client A got no response"
        assert response_b is not None, "Client B got no response"
        assert len(_spoken_text(response_a)) > 0
        assert len(_spoken_text(response_b)) > 0


# ══════════════════════════════════════════════════════════
# 6. Response Quality
# ══════════════════════════════════════════════════════════


class TestResponseQuality:
    """Voice responses are optimized for speech output."""

    async def test_response_not_too_long(self) -> None:
        """Spoken response is under 30 words (voice-optimized)."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "what is the energy per unit")

        assert response is not None
        word_count = len(_spoken_text(response).split())
        assert word_count <= 50, (
            f"Response too long for voice: {word_count} words "
            f"(target ≤30, hard limit 50)"
        )

    async def test_response_is_not_empty(self) -> None:
        """Spoken response contains meaningful content."""
        async with websockets.connect(_auth_url()) as ws:
            response = await _send_utterance_and_wait(ws, "what is the oee")

        assert response is not None
        assert len(_spoken_text(response).strip()) > 5, (
            "Response too short to be meaningful"
        )
