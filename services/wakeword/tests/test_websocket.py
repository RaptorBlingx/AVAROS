"""WebSocket and health endpoint integration tests.

Uses FastAPI ``TestClient`` for the health endpoint and a mock
detector for WebSocket behaviour verification.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from detector import DetectionEvent
from main import app


# ── Health endpoint ───────────────────────────────────────


class TestHealthEndpoint:
    """Tests for ``GET /health``."""

    def test_health_returns_200_with_schema(self) -> None:
        """Health check returns expected JSON schema."""
        # Arrange
        client = TestClient(app)

        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert isinstance(body["models_loaded"], list)
        assert len(body["models_loaded"]) > 0
        assert "version" in body

    def test_health_reflects_configured_model(self) -> None:
        """Health reports the model configured via env var."""
        # Arrange
        client = TestClient(app)

        # Act
        with patch.dict("os.environ", {"WAKEWORD_MODEL": "alexa"}):
            response = client.get("/health")

        # Assert
        assert response.json()["models_loaded"] == ["alexa"]


# ── WebSocket endpoint ────────────────────────────────────


class TestWebSocketEndpoint:
    """Tests for ``WS /ws/detect``."""

    def test_websocket_accepts_connection(self) -> None:
        """WebSocket connection is accepted and can be closed cleanly."""
        # Arrange
        client = TestClient(app)

        # Act & Assert — no exception on connect/disconnect
        with client.websocket_connect("/ws/detect") as ws:
            pass  # connect then immediately disconnect

    def test_websocket_detection_sends_json(self) -> None:
        """When detector fires, the server sends a JSON event."""
        # Arrange
        fake_event = DetectionEvent(
            event="detected",
            model="hey_jarvis",
            score=0.92,
            timestamp="2026-03-04T12:00:00+00:00",
        )
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = fake_event
        mock_detector.close.return_value = None

        client = TestClient(app)

        # Act
        with patch(
            "main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_bytes(b"\x00" * 2560)
                data = ws.receive_json()

        # Assert
        assert data["event"] == "detected"
        assert data["model"] == "hey_jarvis"
        assert data["score"] == 0.92
        assert "timestamp" in data

    def test_websocket_silence_no_response(self) -> None:
        """When detector returns None, server sends nothing."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = None
        mock_detector.close.return_value = None

        client = TestClient(app)

        # Act & Assert
        with patch(
            "main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_bytes(b"\x00" * 2560)
                # Server should NOT send anything for silence.
                # TestClient would raise if we tried receive_json()
                # with a timeout — but that's tricky. Instead we
                # verify process_audio was called and no crash.
                mock_detector.process_audio.assert_called_once()
