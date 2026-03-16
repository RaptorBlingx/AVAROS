import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useHiveMind } from "../../contexts/HiveMindContext";
import { useVoice } from "../../contexts/VoiceContext";
import { useConversation } from "../../hooks/useConversation";
import {
  ONBOARDING_VOICE_FOCUS_EVENT,
  type OnboardingVoiceFocusDetail,
} from "../common/onboarding";
import ChatPanel from "./ChatPanel";
import RecordingIndicator from "./RecordingIndicator";
import brandLogoSrc from "../../assets/logov.svg";
import {
  buildImmediateAssistantReply,
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
import { normalizeUtteranceForIntent } from "../../services/intent-normalizer";
import "./VoiceWidget.css";

type VoiceWidgetProps = {
  position?: WidgetPosition;
};

const RESPONSE_FALLBACK_TIMEOUT_MS = 50000;
const RESPONSE_PROCESSING_TIMEOUT_MS = 70000;
const VOICE_MODE_STORAGE_KEY = "avaros-voice-mode";

export default function VoiceWidget({
  position = "bottom-right",
}: VoiceWidgetProps) {
  const widgetRef = useRef<HTMLElement | null>(null);
  const {
    voiceState,
    voiceMode,
    isWakeWordArmed,
    wakeWordDetectedAt,
    wakeWordState,
    isModelLoading,
    wakeWordLabel,
    micPermission,
    startListening,
    stopListening,
    cancelCurrentQuery,
    finalTranscript,
    speak,
    stopSpeaking,
    requestMicPermission,
    setVoiceMode,
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
    cancelProcessing,
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
  const [ignoreStuckProcessing, setIgnoreStuckProcessing] = useState(false);
  const lastUserUtteranceRef = useRef("");
  const awaitingResponseRef = useRef(false);
  const lastResponseRef = useRef<string | null>(null);
  const displayedResponse = activeResponse ?? responseFallback;
  const {
    messages: conversationMessages,
    isProcessing: isConversationProcessing,
    addUserMessage,
    addAvarosResponse,
    clearConversation,
  } = useConversation();

  const speakAssistantFallback = useCallback(
    (text: string) => {
      if (!ttsSupported || !text.trim()) return;
      stopSpeaking();
      void speak(text).catch(() => undefined);
    },
    [ttsSupported, stopSpeaking, speak],
  );

  const effectiveVoiceState =
    ignoreStuckProcessing && voiceState === "processing" ? "idle" : voiceState;
  const visualState = useMemo(
    () =>
      deriveVisualState({
        isConnected,
        voiceEnabled,
        voiceState: effectiveVoiceState,
        isHiveSpeaking: isHiveSpeaking || isVoiceSpeaking,
        isHiveProcessing: ignoreStuckProcessing ? false : isProcessing,
        localError,
      }),
    [
      isConnected,
      voiceEnabled,
      effectiveVoiceState,
      isHiveSpeaking,
      isVoiceSpeaking,
      isProcessing,
      ignoreStuckProcessing,
      localError,
    ],
  );
  const isWakeWordPassiveListening =
    voiceMode === "wake-word" &&
    visualState === "listening" &&
    !isWakeWordArmed;
  const showRecordingIndicator =
    voiceMode === "wake-word"
      ? isWakeWordArmed &&
        (visualState === "listening" || visualState === "speaking")
      : visualState === "listening" || visualState === "speaking";
  const showHeaderAction =
    voiceMode !== "text" &&
    !(voiceMode === "wake-word" && visualState === "idle") &&
    !isWakeWordPassiveListening;

  useEffect(() => {
    if (wakeWordDetectedAt > 0) {
      setExpanded(true);
    }
  }, [wakeWordDetectedAt]);

  useEffect(() => {
    if (lastResponse) {
      if (voiceMode === "wake-word") {
        setExpanded(true);
      }
      setIgnoreStuckProcessing(false);
      setActiveResponse(lastResponse);
      setResponseReceivedAt(new Date());
      setAwaitingResponse(false);
      setResponseFallback(null);
      setLocalError("");
    }
  }, [lastResponse, voiceMode]);

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
    if (voiceMode === "wake-word") {
      setExpanded(true);
    }
    lastUserUtteranceRef.current = transcript;

    const immediateReply = buildImmediateAssistantReply(transcript);
    if (immediateReply) {
      setIgnoreStuckProcessing(true);
      setActiveResponse(null);
      setResponseReceivedAt(null);
      setAwaitingResponse(false);
      setResponseFallback(immediateReply);
      setLocalError("");
      addAvarosResponse(immediateReply);
      speakAssistantFallback(immediateReply);
      return;
    }

    const guidance = buildGuidanceForUtterance(transcript);
    if (guidance || isLikelyIncompleteUtterance(transcript)) {
      setIgnoreStuckProcessing(true);
      setActiveResponse(null);
      setResponseReceivedAt(null);
      setAwaitingResponse(false);
      const fallbackText =
        guidance ??
        "Incomplete voice command. Try: 'what if we increase temperature by 5 degrees'.";
      setResponseFallback(fallbackText);
      setLocalError("");
      addAvarosResponse(fallbackText);
      speakAssistantFallback(fallbackText);
      return;
    }

    setIgnoreStuckProcessing(false);
    setActiveResponse(null);
    setResponseReceivedAt(null);
    setAwaitingResponse(true);
    setResponseFallback(null);
    setLocalError("");
  }, [finalTranscript, addAvarosResponse, voiceMode, speakAssistantFallback]);

  useEffect(() => {
    awaitingResponseRef.current = awaitingResponse;
  }, [awaitingResponse]);

  useEffect(() => {
    lastResponseRef.current = lastResponse;
  }, [lastResponse]);

  useEffect(() => {
    if (!awaitingResponse) {
      return;
    }

    const timeoutMs = isProcessing
      ? RESPONSE_PROCESSING_TIMEOUT_MS
      : RESPONSE_FALLBACK_TIMEOUT_MS;

    const timer = window.setTimeout(() => {
      // Guard against stale timeout callback when response already arrived.
      if (!awaitingResponseRef.current || lastResponseRef.current) {
        return;
      }
      setIgnoreStuckProcessing(true);
      cancelCurrentQuery();
      setAwaitingResponse(false);
      const guidance = buildGuidanceForUtterance(lastUserUtteranceRef.current);
      const fallbackText =
        guidance ??
        "I couldn't match that request yet. Try: 'show energy trend today', 'check production anomalies', or 'compare energy'.";
      setResponseFallback(fallbackText);
      setLocalError("");
      addAvarosResponse(fallbackText);
      speakAssistantFallback(fallbackText);
    }, timeoutMs);

    return () => window.clearTimeout(timer);
  }, [
    awaitingResponse,
    isProcessing,
    addAvarosResponse,
    cancelCurrentQuery,
    speakAssistantFallback,
  ]);

  useEffect(() => {
    if (awaitingResponse || effectiveVoiceState !== "processing") {
      return;
    }
    const timer = window.setTimeout(() => {
      if (awaitingResponseRef.current) return;
      cancelCurrentQuery();
      setIgnoreStuckProcessing(true);
      setAwaitingResponse(false);
    }, RESPONSE_FALLBACK_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [awaitingResponse, effectiveVoiceState, cancelCurrentQuery]);

  const handleCancelRequest = useCallback(() => {
    cancelCurrentQuery();
    cancelProcessing();
    setAwaitingResponse(false);
    setIgnoreStuckProcessing(true);
    setActiveResponse(null);
    setResponseReceivedAt(null);
    setLocalError("");
    const fallbackText = "Request cancelled.";
    setResponseFallback(fallbackText);
    addAvarosResponse(fallbackText);
    speakAssistantFallback(fallbackText);
  }, [
    cancelCurrentQuery,
    cancelProcessing,
    addAvarosResponse,
    speakAssistantFallback,
  ]);

  useEffect(() => {
    if (!expanded) {
      return;
    }

    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (visualState === "listening" && voiceMode !== "wake-word") {
        stopListening();
      }
      if (visualState === "speaking") stopSpeaking();
      if (visualState === "processing") handleCancelRequest();
      if (voiceMode === "wake-word") {
        cancelCurrentQuery();
        void setVoiceMode("wake-word").catch(() => undefined);
      }
      setExpanded(false);
    };

    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [
    expanded,
    visualState,
    stopListening,
    stopSpeaking,
    handleCancelRequest,
    voiceMode,
    cancelCurrentQuery,
  ]);

  useEffect(() => {
    const onOnboardingVoiceFocus = (event: Event) => {
      const detail = (event as CustomEvent<OnboardingVoiceFocusDetail>).detail;
      if (!detail) return;
      setExpanded(detail.expanded);
      if (!detail.expanded) {
        if (visualState === "listening" && voiceMode !== "wake-word") {
          stopListening();
        }
        if (visualState === "speaking") stopSpeaking();
        if (voiceMode === "wake-word") {
          cancelCurrentQuery();
          void setVoiceMode("wake-word").catch(() => undefined);
        }
      }
    };
    window.addEventListener(
      ONBOARDING_VOICE_FOCUS_EVENT,
      onOnboardingVoiceFocus,
    );
    return () => {
      window.removeEventListener(
        ONBOARDING_VOICE_FOCUS_EVENT,
        onOnboardingVoiceFocus,
      );
    };
  }, [
    visualState,
    stopListening,
    stopSpeaking,
    voiceMode,
    cancelCurrentQuery,
    setVoiceMode,
  ]);

  useEffect(() => {
    if (!expanded) return;

    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (widgetRef.current?.contains(target)) return;

      if (visualState === "listening" && voiceMode !== "wake-word") {
        stopListening();
      }
      if (visualState === "speaking") stopSpeaking();
      if (voiceMode === "wake-word") {
        cancelCurrentQuery();
        void setVoiceMode("wake-word").catch(() => undefined);
      }
      setExpanded(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown, { passive: true });
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
    };
  }, [
    expanded,
    visualState,
    stopListening,
    stopSpeaking,
    voiceMode,
    cancelCurrentQuery,
    setVoiceMode,
  ]);

  const requestListening = useCallback(async () => {
    setIgnoreStuckProcessing(false);
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
      return;
    }

    if (visualState === "listening" && voiceMode !== "wake-word") {
      stopListening();
    }
    if (visualState === "speaking") stopSpeaking();
    if (voiceMode === "wake-word") {
      cancelCurrentQuery();
      void setVoiceMode("wake-word").catch(() => undefined);
    }
    setExpanded(false);
  }, [
    expanded,
    visualState,
    stopListening,
    stopSpeaking,
    voiceMode,
    cancelCurrentQuery,
    setVoiceMode,
  ]);

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
      handleCancelRequest();
      return;
    }

    void requestListening();
  }, [
    requestListening,
    stopListening,
    stopSpeaking,
    handleCancelRequest,
    visualState,
  ]);

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
      const original = text.trim();
      if (!original) return;
      const normalized = normalizeUtteranceForIntent(original);
      lastUserUtteranceRef.current = normalized;

      const immediateReply = buildImmediateAssistantReply(normalized);
      if (immediateReply) {
        setIgnoreStuckProcessing(true);
        setLocalError("");
        setActiveResponse(null);
        setResponseReceivedAt(null);
        setAwaitingResponse(false);
        setResponseFallback(immediateReply);
        addUserMessage(original, "text");
        addAvarosResponse(immediateReply);
        speakAssistantFallback(immediateReply);
        return;
      }

      const guidance = buildGuidanceForUtterance(normalized);
      if (guidance) {
        setIgnoreStuckProcessing(true);
        setLocalError("");
        setActiveResponse(null);
        setResponseReceivedAt(null);
        setAwaitingResponse(false);
        setResponseFallback(guidance);
        addUserMessage(original, "text");
        addAvarosResponse(guidance);
        speakAssistantFallback(guidance);
        return;
      }

      setIgnoreStuckProcessing(false);
      setLocalError("");
      setActiveResponse(null);
      setResponseReceivedAt(null);
      setAwaitingResponse(true);
      setResponseFallback(null);
      addUserMessage(original, "text");

      try {
        await sendUtterance(normalized);
      } catch {
        setAwaitingResponse(false);
        setLocalError("");
        const fallbackText =
          "I can't send this right now. Check HiveMind connection and try again.";
        setResponseFallback(fallbackText);
        addAvarosResponse(fallbackText);
        speakAssistantFallback(fallbackText);
      }
    },
    [addUserMessage, addAvarosResponse, sendUtterance, speakAssistantFallback],
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
        data-onboarding-target="voice-widget-trigger"
      >
        <RecordingIndicator
          active={showRecordingIndicator}
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
          data-onboarding-target="voice-widget-panel"
        >
          <header className="voice-widget__header">
            <div className="flex flex-row gap-4">
              <img src={brandLogoSrc} alt="AVAROS" className="w-10 h-10" />

              <div className="voice-widget__header-left">
                <p className="voice-widget__title">Voice Assistant</p>
                <p className="voice-widget__state" aria-live="polite">
                  {STATE_META[visualState].label}
                </p>
              </div>
            </div>
            {showHeaderAction && (
              <button
                type="button"
                className={`voice-widget__header-action voice-widget__header-action--${visualState}`}
                onClick={handlePrimaryAction}
                disabled={visualState === "disconnected"}
                title={
                  visualState === "processing"
                    ? "Cancel current request"
                    : buttonTitle
                }
                aria-label={getActionLabel(visualState)}
              >
                <span
                  className="voice-widget__header-action__icon"
                  aria-hidden="true"
                >
                  {renderStateIcon(visualState)}
                </span>
                <span className="voice-widget__header-action__label">
                  {getActionLabel(visualState)}
                </span>
              </button>
            )}
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

          <ChatPanel
            messages={conversationMessages}
            isProcessing={isConversationProcessing}
            isConnected={isConnected && voiceEnabled}
            canReplay={ttsSupported}
            wakeWordLabel={wakeWordLabel}
            onSendText={handleSendText}
            onReplayResponse={handleReplayMessage}
            onClearConversation={clearConversation}
          />
        </section>
      )}
    </aside>
  );
}
