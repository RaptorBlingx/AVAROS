import { useCallback, useEffect, useMemo, useState } from "react";

import { useHiveMind } from "../../contexts/HiveMindContext";
import { useVoice } from "../../contexts/VoiceContext";
import RecordingIndicator from "./RecordingIndicator";
import ResponseDisplay from "./ResponseDisplay";
import TranscriptDisplay from "./TranscriptDisplay";
import {
  MICROPHONE_HELP_URL,
  POSITION_CLASS,
  STATE_META,
  deriveVisualState,
  getActionLabel,
  isLikelyIncompleteUtterance,
  renderStateIcon,
  type WidgetPosition,
} from "./voiceWidget.helpers";
import "./VoiceWidget.css";

type VoiceWidgetProps = {
  position?: WidgetPosition;
};

export default function VoiceWidget({
  position = "bottom-right",
}: VoiceWidgetProps) {
  const {
    voiceState,
    micPermission,
    startListening,
    stopListening,
    interimTranscript,
    finalTranscript,
    speak,
    stopSpeaking,
    requestMicPermission,
    sttSupported,
    ttsSupported,
    isSpeaking: isVoiceSpeaking,
  } = useVoice();
  const {
    connectionState,
    isConnected,
    lastResponse,
    isSpeaking: isHiveSpeaking,
    isProcessing,
    voiceEnabled,
  } = useHiveMind();

  const [expanded, setExpanded] = useState(false);
  const [permissionMessage, setPermissionMessage] = useState("");
  const [localError, setLocalError] = useState("");
  const [responseReceivedAt, setResponseReceivedAt] = useState<Date | null>(
    null,
  );
  const [awaitingResponse, setAwaitingResponse] = useState(false);
  const [responseFallback, setResponseFallback] = useState<string | null>(null);
  const [activeResponse, setActiveResponse] = useState<string | null>(null);
  const displayedResponse = activeResponse ?? responseFallback;

  const visualState = useMemo(
    () =>
      deriveVisualState({
        isConnected,
        voiceEnabled,
        voiceState,
        isHiveSpeaking: isHiveSpeaking || isVoiceSpeaking,
        isHiveProcessing: isProcessing,
        localError,
      }),
    [
      isConnected,
      voiceEnabled,
      voiceState,
      isHiveSpeaking,
      isVoiceSpeaking,
      isProcessing,
      localError,
    ],
  );

  useEffect(() => {
    if (lastResponse) {
      setActiveResponse(lastResponse);
      setResponseReceivedAt(new Date());
      setAwaitingResponse(false);
      setResponseFallback(null);
      setLocalError("");
    }
  }, [lastResponse]);

  // If a response is being spoken but text did not change (same reply as previous),
  // keep the widget out of timeout by reusing the latest known response.
  useEffect(() => {
    if (!awaitingResponse) return;
    if (visualState !== "speaking") return;
    if (!lastResponse) return;

    setActiveResponse(lastResponse);
    setResponseReceivedAt(new Date());
    setAwaitingResponse(false);
    setResponseFallback(null);
    setLocalError("");
  }, [awaitingResponse, visualState, lastResponse]);

  useEffect(() => {
    const transcript = finalTranscript.trim();
    if (!transcript) return;

    if (isLikelyIncompleteUtterance(transcript)) {
      setActiveResponse(null);
      setResponseReceivedAt(null);
      setAwaitingResponse(false);
      setResponseFallback(
        "Incomplete voice command. Try: 'what if we increase temperature by 5 degrees'.",
      );
      setLocalError("Please speak a complete command.");
      return;
    }

    setActiveResponse(null);
    setResponseReceivedAt(null);
    setAwaitingResponse(true);
    setResponseFallback(null);
    setLocalError("");
  }, [finalTranscript]);

  useEffect(() => {
    if (!awaitingResponse) {
      return;
    }

    const timer = window.setTimeout(() => {
      setAwaitingResponse(false);
      setResponseFallback(
        "No response from AVAROS for this utterance. Try another command.",
      );
      setLocalError("No response received. Please try a different command.");
    }, 7000);

    return () => window.clearTimeout(timer);
  }, [awaitingResponse]);

  useEffect(() => {
    if (!expanded) {
      return;
    }

    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (visualState === "listening") stopListening();
      if (visualState === "speaking") stopSpeaking();
      setExpanded(false);
    };

    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [expanded, visualState, stopListening, stopSpeaking]);

  const requestListening = useCallback(async () => {
    setLocalError("");

    if (!voiceEnabled || !isConnected || connectionState === "connecting") {
      setLocalError("Voice unavailable. HiveMind is not connected.");
      return;
    }

    if (!sttSupported) {
      setLocalError("Speech recognition is not supported in this browser.");
      return;
    }

    if (micPermission === "unsupported") {
      setLocalError("Microphone is unavailable on this device.");
      return;
    }

    if (micPermission === "denied") {
      setLocalError("Microphone access denied. Use text mode instead.");
      return;
    }

    if (micPermission === "prompt") {
      setPermissionMessage(
        "AVAROS needs microphone access for voice interaction.",
      );
      const permission = await requestMicPermission();
      if (permission !== "granted") {
        setLocalError("Microphone access denied. Use text mode instead.");
        return;
      }
    }

    setPermissionMessage("");
    await startListening();
  }, [
    voiceEnabled,
    isConnected,
    connectionState,
    sttSupported,
    micPermission,
    requestMicPermission,
    startListening,
  ]);

  const handleMicClick = useCallback(() => {
    if (!expanded) {
      setExpanded(true);
      if (
        visualState === "idle" ||
        visualState === "error" ||
        visualState === "disconnected"
      ) {
        void requestListening();
      }
      return;
    }

    if (visualState === "listening") stopListening();
    if (visualState === "speaking") stopSpeaking();
    setExpanded(false);
  }, [expanded, visualState, requestListening, stopListening, stopSpeaking]);

  const handlePrimaryAction = useCallback(() => {
    if (visualState === "listening") {
      stopListening();
      return;
    }

    if (visualState === "speaking") {
      stopSpeaking();
      return;
    }

    if (visualState === "processing") {
      return;
    }

    void requestListening();
  }, [requestListening, stopListening, stopSpeaking, visualState]);

  const handleReplay = useCallback(() => {
    if (!displayedResponse || !ttsSupported) {
      return;
    }
    setLocalError("");
    stopSpeaking();
    void speak(displayedResponse).catch(() => {
      setLocalError("Could not replay the response.");
    });
  }, [displayedResponse, ttsSupported, speak, stopSpeaking]);

  const buttonTitle =
    localError ||
    (micPermission === "denied"
      ? "Microphone blocked. Enable in browser settings."
      : STATE_META[visualState].hint);

  return (
    <aside
      className={`voice-widget !mr-4 ${POSITION_CLASS[position]} ${
        expanded ? "voice-widget--expanded" : ""
      }`}
    >
      <button
        type="button"
        className={`voice-widget__button voice-widget__button--${visualState}`}
        onClick={handleMicClick}
        aria-label={expanded ? "Minimize voice widget" : "Open voice widget"}
        title={buttonTitle}
      >
        <RecordingIndicator
          active={visualState === "listening" || visualState === "speaking"}
          variant={visualState === "speaking" ? "speaking" : "listening"}
        />
        {renderStateIcon(visualState)}
        <span
          className={`voice-widget__dot voice-widget__dot--${visualState}`}
          aria-hidden="true"
        />
      </button>

      {expanded && (
        <section
          className="voice-widget__panel !mr-4"
          aria-label="Voice interaction panel"
        >
          <header className="voice-widget__header">
            <div>
              <p className="voice-widget__title">Voice Assistant</p>
              <p className="voice-widget__state">
                {STATE_META[visualState].label}
              </p>
            </div>
            <button
              type="button"
              className="voice-widget__minimize"
              onClick={() => setExpanded(false)}
              aria-label="Minimize voice panel"
            >
              −
            </button>
          </header>

          {permissionMessage && (
            <p className="voice-widget__notice">{permissionMessage}</p>
          )}

          {localError && (
            <p className="voice-widget__error">
              {localError}{" "}
              {micPermission === "denied" && (
                <a href={MICROPHONE_HELP_URL} target="_blank" rel="noreferrer">
                  Open browser help
                </a>
              )}
            </p>
          )}

          <TranscriptDisplay
            interimTranscript={interimTranscript}
            finalTranscript={finalTranscript}
            listening={visualState === "listening"}
          />

          <ResponseDisplay
            responseText={displayedResponse}
            isSpeaking={visualState === "speaking"}
            receivedAt={responseReceivedAt}
            canReplay={Boolean(displayedResponse && ttsSupported)}
            onReplay={handleReplay}
          />

          <div className="voice-widget__actions">
            <button
              type="button"
              className="voice-widget__action"
              onClick={handlePrimaryAction}
              disabled={
                visualState === "processing" || visualState === "disconnected"
              }
            >
              {getActionLabel(visualState)}
            </button>
          </div>
        </section>
      )}
    </aside>
  );
}
