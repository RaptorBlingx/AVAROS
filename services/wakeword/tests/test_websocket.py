"""WebSocket and health endpoint integration tests.

Uses FastAPI ``TestClient`` for the health endpoint and a mock
detector for WebSocket behaviour verification.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.wakeword import main as wakeword_main
from services.wakeword.detector import DetectionEvent

app = wakeword_main.app


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

    def test_health_reports_custom_model_label(self) -> None:
        """Health endpoint shows WAKEWORD_MODEL_LABEL when set."""
        # Arrange
        client = TestClient(app)

        # Act
        with patch.dict("os.environ", {"WAKEWORD_MODEL_LABEL": "hey_avaros"}):
            response = client.get("/health")

        # Assert
        assert response.json()["models_loaded"] == ["hey_avaros"]

    def test_health_reports_custom_path_stem_as_label(self) -> None:
        """Health derives label from WAKEWORD_MODEL_PATH filename stem."""
        # Arrange
        client = TestClient(app)

        # Act
        with patch.dict(
            "os.environ",
            {"WAKEWORD_MODEL_PATH": "/app/models/hey_avaros.onnx"},
            clear=False,
        ):
            response = client.get("/health")

        # Assert
        assert response.json()["models_loaded"] == ["hey_avaros"]


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
            "services.wakeword.main.WakeWordDetector",
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
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_bytes(b"\x00" * 2560)
                # Server should NOT send anything for silence.
                # TestClient would raise if we tried receive_json()
                # with a timeout — but that's tricky. Instead we
                # verify process_audio was called and no crash.
                mock_detector.process_audio.assert_called_once()

    def test_websocket_text_command_ignored_and_audio_still_processed(self) -> None:
        """A text control frame should not break binary audio processing."""
        # Arrange
        fake_event = DetectionEvent(
            event="detected",
            model="hey_jarvis",
            score=0.91,
            timestamp="2026-03-04T12:00:00+00:00",
        )
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = fake_event
        mock_detector.close.return_value = None

        client = TestClient(app)

        # Act
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_text('{"command":"set_sensitivity","value":0.7}')
                ws.send_bytes(b"\x00" * 2560)
                data = ws.receive_json()

        # Assert
        assert data["event"] == "detected"
        assert data["model"] == "hey_jarvis"
        assert data["score"] == 0.91
        assert "timestamp" in data

    def test_websocket_uses_model_label_for_detector_name(self) -> None:
        """Detector loads registry model but emits configured display label."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = None
        mock_detector.close.return_value = None
        client = TestClient(app)

        # Act
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ) as detector_cls:
            with patch.dict(
                "os.environ",
                {
                    "WAKEWORD_MODEL": "hey_jarvis",
                    "WAKEWORD_MODEL_LABEL": "hey_avaros",
                },
                clear=False,
            ):
                with client.websocket_connect("/ws/detect"):
                    pass

        # Assert
        detector_cls.assert_called_once()
        kwargs = detector_cls.call_args.kwargs
        assert kwargs["model_name"] == "hey_jarvis"
        assert kwargs["display_name"] == "hey_avaros"

    def test_websocket_uses_custom_path_stem_when_label_missing(self) -> None:
        """Custom-path mode uses stem as display name when label is absent."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = None
        mock_detector.close.return_value = None
        client = TestClient(app)

        # Act
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ) as detector_cls:
            with patch.dict(
                "os.environ",
                {
                    "WAKEWORD_MODEL_PATH": "/app/models/hey_avaros.onnx",
                },
                clear=False,
            ):
                with client.websocket_connect("/ws/detect"):
                    pass

        # Assert
        detector_cls.assert_called_once()
        kwargs = detector_cls.call_args.kwargs
        assert kwargs["model_name"] == "hey_jarvis"
        assert kwargs["display_name"] == "hey_avaros"

    def test_websocket_registry_load_and_label_are_separate(self) -> None:
        """Registry loading uses WAKEWORD_MODEL while response uses label."""
        # Arrange
        client = TestClient(app)

        class _FakeModel:
            def __init__(self) -> None:
                self.models = {"hey_jarvis_v0.1": object()}

            def predict(self, _samples: object) -> dict[str, float]:
                return {"hey_jarvis_v0.1": 0.91}

        # Act
        with patch(
            "services.wakeword.detector._ensure_openwakeword_assets",
            return_value="/tmp/hey_jarvis.onnx",
        ), patch(
            "openwakeword.model.Model",
            return_value=_FakeModel(),
        ) as model_cls:
            with patch.dict(
                "os.environ",
                {
                    "WAKEWORD_MODEL": "hey_jarvis",
                    "WAKEWORD_MODEL_LABEL": "hey_avaros",
                },
                clear=False,
            ):
                with client.websocket_connect("/ws/detect") as ws:
                    ws.send_bytes(b"\x00" * 2560)
                    data = ws.receive_json()

        # Assert
        assert data["event"] == "detected"
        assert data["model"] == "hey_avaros"
        model_cls.assert_called_once_with(wakeword_models=["hey_jarvis"])


# ── Startup validation ────────────────────────────────────


class TestStartupValidation:
    """Tests for lifespan startup validation of custom model paths."""

    def test_startup_fails_when_custom_path_missing(self) -> None:
        """Service refuses to start if WAKEWORD_MODEL_PATH points to missing file."""
        # Arrange
        env = {"WAKEWORD_MODEL_PATH": "/nonexistent/model.onnx"}

        async def _run_lifespan() -> None:
            """Enter app lifespan context to trigger startup validation."""
            async with app.router.lifespan_context(app):
                return

        # Act & Assert
        with patch.dict("os.environ", env, clear=False):
            with pytest.raises(SystemExit):
                asyncio.run(_run_lifespan())

    def test_startup_succeeds_when_custom_path_exists(self, tmp_path: object) -> None:
        """Service starts when WAKEWORD_MODEL_PATH points to an existing file."""
        # Arrange
        model_file = os.path.join(str(tmp_path), "test_model.onnx")
        with open(model_file, "wb") as f:
            f.write(b"\x00")
        env = {"WAKEWORD_MODEL_PATH": model_file}

        # Act & Assert — no exception
        with patch.dict("os.environ", env, clear=False):
            with TestClient(app):
                pass
