"""WebSocket and health endpoint integration tests.

Uses FastAPI ``TestClient`` for the health endpoint and a mock
detector for WebSocket behaviour verification.
"""

from __future__ import annotations

import asyncio
import os
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.wakeword import main as wakeword_main
from services.wakeword.detector import DEFAULT_CONFIRMATION_FRAMES
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
        assert "model_mode" in body
        assert "threshold" in body
        assert "threshold_source" in body
        assert "confirmation_frames" in body

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
            model="hey_avaros",
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
        assert data["model"] == "hey_avaros"
        assert data["score"] == 0.92
        assert "timestamp" in data

    def test_websocket_silence_no_response(self) -> None:
        """When detector returns None, server sends nothing."""
        # Arrange
        processed = threading.Event()
        mock_detector = MagicMock()

        def _process_audio(_payload: bytes) -> None:
            processed.set()
            return None

        mock_detector.process_audio.side_effect = _process_audio
        mock_detector.close.return_value = None

        client = TestClient(app)

        # Act & Assert
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_bytes(b"\x00" * 2560)
                assert processed.wait(timeout=0.5)
                mock_detector.process_audio.assert_called_once()

    def test_websocket_text_command_ignored_and_audio_still_processed(self) -> None:
        """A text control frame should not break binary audio processing."""
        # Arrange
        fake_event = DetectionEvent(
            event="detected",
            model="hey_avaros",
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
        assert data["model"] == "hey_avaros"
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
                    "WAKEWORD_MODEL": "hey_avaros",
                    "WAKEWORD_MODEL_LABEL": "hey_avaros",
                },
                clear=False,
            ):
                with client.websocket_connect("/ws/detect"):
                    pass

        # Assert
        detector_cls.assert_called_once()
        kwargs = detector_cls.call_args.kwargs
        assert kwargs["model_name"] == "hey_avaros"
        assert kwargs["display_name"] == "hey_avaros"

    def test_websocket_uses_custom_path_stem_when_label_missing(self) -> None:
        """Custom-path mode uses stem as display name when label is absent."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = None
        mock_detector.close.return_value = None
        client = TestClient(app)

        # Act — env patch outermost so it is visible to ASGI thread
        with patch.dict(
            "os.environ",
            {
                "WAKEWORD_MODEL": "hey_avaros",
                "WAKEWORD_MODEL_PATH": "/app/models/hey_avaros.onnx",
            },
            clear=False,
        ):
            with patch(
                "services.wakeword.main.WakeWordDetector",
                return_value=mock_detector,
            ) as detector_cls:
                with client.websocket_connect("/ws/detect"):
                    pass

        # Assert
        detector_cls.assert_called_once()
        kwargs = detector_cls.call_args.kwargs
        assert kwargs["model_name"] == "hey_avaros"
        assert kwargs["display_name"] == "hey_avaros"

    def test_websocket_registry_load_and_label_are_separate(self) -> None:
        """Registry loading uses WAKEWORD_MODEL while response uses label."""
        # Arrange
        client = TestClient(app)

        class _FakeModel:
            def __init__(self) -> None:
                self.models = {"alexa_v0.1": object()}

            def predict(self, _samples: object) -> dict[str, float]:
                return {"alexa_v0.1": 0.91}

        # Act
        with patch(
            "services.wakeword.detector._ensure_openwakeword_assets",
            return_value="/tmp/alexa.onnx",
        ), patch(
            "openwakeword.model.Model",
            return_value=_FakeModel(),
        ) as model_cls:
            with patch.dict(
                "os.environ",
                {
                    "WAKEWORD_MODEL": "alexa",
                    "WAKEWORD_MODEL_LABEL": "hey_avaros",
                },
                clear=False,
            ):
                with client.websocket_connect("/ws/detect") as ws:
                    # Detection requires sustained confidence across
                    # multiple frames (confirmation window).
                    for _ in range(DEFAULT_CONFIRMATION_FRAMES):
                        ws.send_bytes(b"\x00" * 2560)
                    data = ws.receive_json()

        # Assert
        assert data["event"] == "detected"
        assert data["model"] == "hey_avaros"
        model_cls.assert_called_once_with(wakeword_models=["alexa"])


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


# ── Health metadata tests ─────────────────────────────────


class TestHealthMetadata:
    """Tests for enhanced runtime configuration in health output."""

    def test_health_reports_custom_path_mode(self) -> None:
        """Health shows model_mode='custom_path' when WAKEWORD_MODEL_PATH set."""
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
        assert response.json()["model_mode"] == "custom_path"

    def test_health_reports_registry_mode(self) -> None:
        """Health shows model_mode='registry' when no custom path set."""
        # Arrange
        client = TestClient(app)

        # Act
        with patch.dict("os.environ", {}, clear=False):
            # Ensure WAKEWORD_MODEL_PATH is absent
            env_copy = dict(os.environ)
            env_copy.pop("WAKEWORD_MODEL_PATH", None)
            with patch.dict("os.environ", env_copy, clear=True):
                response = client.get("/health")

        # Assert
        assert response.json()["model_mode"] == "registry"

    def test_health_reports_threshold(self) -> None:
        """Health response includes the configured threshold."""
        # Arrange
        client = TestClient(app)

        # Act
        with patch.dict("os.environ", {"WAKEWORD_THRESHOLD": "0.7"}, clear=False):
            response = client.get("/health")

        # Assert
        assert response.json()["threshold"] == 0.7
        assert response.json()["configured_threshold"] == 0.7
        assert response.json()["threshold_source"] == "configured"
        assert response.json()["active_session_threshold_min"] == 0.7
        assert response.json()["active_session_threshold_max"] == 0.7
        assert response.json()["active_session_threshold_avg"] == 0.7

    def test_health_reports_confirmation_frames(self) -> None:
        """Health response includes confirmation_frames config."""
        # Arrange
        client = TestClient(app)

        # Act
        with patch.dict(
            "os.environ",
            {"WAKEWORD_CONFIRMATION_FRAMES": "5"},
            clear=False,
        ):
            response = client.get("/health")

        # Assert
        assert response.json()["confirmation_frames"] == 5

    def test_health_reports_active_runtime_threshold_for_live_session(self) -> None:
        """Health reflects runtime threshold after websocket updates."""
        # Arrange
        threshold_updated = threading.Event()
        client = TestClient(app)

        class _FakeDetector:
            def __init__(self) -> None:
                self.current_threshold = 0.5

            @property
            def config_info(self) -> dict[str, float]:
                return {"threshold": self.current_threshold}

            def update_threshold(self, value: float) -> None:
                self.current_threshold = value
                threshold_updated.set()

            def process_audio(self, _payload: bytes) -> None:
                return None

            def close(self) -> None:
                return None

        fake_detector = _FakeDetector()

        # Act
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=fake_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_text('{"command":"set_threshold","value":0.72}')
                assert threshold_updated.wait(timeout=0.5)
                response = client.get("/health")

                # Assert
                body = response.json()
                assert body["threshold"] == 0.72
                assert body["threshold_source"] == "active_session_avg"
                assert body["active_session_count"] == 1
                assert body["active_session_thresholds"] == [0.72]
                assert body["active_session_threshold_min"] == 0.72
                assert body["active_session_threshold_max"] == 0.72
                assert body["active_session_threshold_avg"] == 0.72


# ── WebSocket sensitivity / threshold handling ────────────


class TestWebSocketSensitivity:
    """Tests for real set_sensitivity and set_threshold WS commands."""

    def test_set_sensitivity_updates_detector_threshold(self) -> None:
        """set_sensitivity command updates detector via update_threshold."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = None
        mock_detector.close.return_value = None
        client = TestClient(app)

        # Act
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_text('{"command":"set_sensitivity","value":0.75}')
                # Send audio to keep loop alive then disconnect
                ws.send_bytes(b"\x00" * 2560)

        # Assert — sensitivity 0.75 → threshold 0.25 (inverted)
        mock_detector.update_threshold.assert_called_once_with(0.25)

    def test_set_threshold_updates_detector_directly(self) -> None:
        """set_threshold command updates detector threshold directly."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = None
        mock_detector.close.return_value = None
        client = TestClient(app)

        # Act
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_text('{"command":"set_threshold","value":0.65}')
                ws.send_bytes(b"\x00" * 2560)

        # Assert
        mock_detector.update_threshold.assert_called_once_with(0.65)

    def test_set_sensitivity_ignores_missing_value(self) -> None:
        """set_sensitivity without a value does not crash."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.process_audio.return_value = None
        mock_detector.close.return_value = None
        client = TestClient(app)

        # Act — no crash
        with patch(
            "services.wakeword.main.WakeWordDetector",
            return_value=mock_detector,
        ):
            with client.websocket_connect("/ws/detect") as ws:
                ws.send_text('{"command":"set_sensitivity"}')
                ws.send_bytes(b"\x00" * 2560)

        # Assert — update_threshold never called
        mock_detector.update_threshold.assert_not_called()
