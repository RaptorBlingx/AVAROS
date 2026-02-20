import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useHiveMind } from "../../contexts/HiveMindContext";
import { useVoice } from "../../contexts/VoiceContext";
import { useConversation } from "../../hooks/useConversation";
import ChatPanel from "./ChatPanel";
import RecordingIndicator from "./RecordingIndicator";
import ResponseDisplay from "./ResponseDisplay";
import TranscriptDisplay from "./TranscriptDisplay";
import {
  buildGuidanceForUtterance,
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
  const widgetRef = useRef<HTMLElement | null>(null);
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
    sendUtterance,
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
  const lastUserUtteranceRef = useRef("");
  const displayedResponse = activeResponse ?? responseFallback;
  const {
    messages: conversationMessages,
    isProcessing: isConversationProcessing,
    addUserMessage,
    addAvarosResponse,
    clearConversation,
  } = useConversation();

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
    lastUserUtteranceRef.current = transcript;

    const guidance = buildGuidanceForUtterance(transcript);
    if (guidance || isLikelyIncompleteUtterance(transcript)) {
      setActiveResponse(null);
      setResponseReceivedAt(null);
      setAwaitingResponse(false);
      const fallbackText =
        guidance ??
        "Incomplete voice command. Try: 'what if we increase temperature by 5 degrees'.";
      setResponseFallback(fallbackText);
      setLocalError("");
      addAvarosResponse(fallbackText);
      return;
    }

    setActiveResponse(null);
    setResponseReceivedAt(null);
    setAwaitingResponse(true);
    setResponseFallback(null);
    setLocalError("");
  }, [finalTranscript, addAvarosResponse]);

  useEffect(() => {
    if (!awaitingResponse) {
      return;
    }

    const timer = window.setTimeout(() => {
      setAwaitingResponse(false);
      const guidance = buildGuidanceForUtterance(lastUserUtteranceRef.current);
      const fallbackText =
        guidance ??
        "I couldn't match that request yet. Try: 'show energy trend today', 'check production anomaly', or 'compare energy'.";
      setResponseFallback(fallbackText);
      setLocalError("");
      addAvarosResponse(fallbackText);
    }, 7000);

    return () => window.clearTimeout(timer);
  }, [awaitingResponse, addAvarosResponse]);

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

  useEffect(() => {
    if (!expanded) return;

    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (widgetRef.current?.contains(target)) return;

      if (visualState === "listening") stopListening();
      if (visualState === "speaking") stopSpeaking();
      setExpanded(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown, { passive: true });
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
    };
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

  const handleReplayMessage = useCallback(
    (text: string) => {
      if (!ttsSupported || !text.trim()) return;
      setLocalError("");
      stopSpeaking();
      void speak(text).catch(() => {
        setLocalError("Could not replay the response.");
      });
    },
    [ttsSupported, stopSpeaking, speak],
  );

  const handleSendText = useCallback(
    async (text: string) => {
      const normalized = text.trim();
      if (!normalized) return;
      lastUserUtteranceRef.current = normalized;

      const guidance = buildGuidanceForUtterance(normalized);
      if (guidance) {
        setLocalError("");
        setActiveResponse(null);
        setResponseReceivedAt(null);
        setAwaitingResponse(false);
        setResponseFallback(guidance);
        addUserMessage(normalized, "text");
        addAvarosResponse(guidance);
        return;
      }

      setLocalError("");
      setActiveResponse(null);
      setResponseReceivedAt(null);
      setAwaitingResponse(true);
      setResponseFallback(null);
      addUserMessage(normalized, "text");

      try {
        await sendUtterance(normalized);
      } catch {
        setAwaitingResponse(false);
        setLocalError("");
        const fallbackText =
          "I can't send this right now. Check HiveMind connection and try again.";
        setResponseFallback(fallbackText);
        addAvarosResponse(fallbackText);
      }
    },
    [addUserMessage, addAvarosResponse, sendUtterance],
  );

  const buttonTitle =
    localError ||
    (micPermission === "denied"
      ? "Microphone blocked. Enable in browser settings."
      : STATE_META[visualState].hint);

  return (
    <aside
      ref={widgetRef}
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

          <ChatPanel
            messages={conversationMessages}
            isProcessing={isConversationProcessing}
            isConnected={isConnected && voiceEnabled}
            canReplay={ttsSupported}
            onSendText={handleSendText}
            onReplayResponse={handleReplayMessage}
            onClearConversation={clearConversation}
          />
        </section>
      )}
    </aside>
  );
}
