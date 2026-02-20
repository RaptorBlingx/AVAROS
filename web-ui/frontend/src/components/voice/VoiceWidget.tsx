/**
 * VoiceWidget — floating mic button with expandable transcript/response panel.
 *
 * Renders a fixed-position circular microphone button that toggles between
 * minimized (icon + status dot) and expanded (transcript + response) views.
 * Integrates with useVoice() and useHiveMind() contexts for all voice logic.
 *
 * Visual states: idle, listening, processing, speaking, error, disconnected.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { useHiveMind } from "../../contexts/HiveMindContext";
import { useVoice } from "../../contexts/VoiceContext";
import RecordingIndicator from "./RecordingIndicator";
import ResponseDisplay from "./ResponseDisplay";
import TranscriptDisplay from "./TranscriptDisplay";
import {
  type DerivedState,
  type WidgetPosition,
  dotClasses,
  micAnimationClass,
  micColorClasses,
  micTooltip,
  panelPositionClasses,
  positionClasses,
  stateLabel,
} from "./voice-widget-helpers";
import { CloseIcon, MicIcon, MicOffIcon, SpeakerIcon } from "./VoiceWidgetIcons";
import "./VoiceWidget.css";

// ── Types ──────────────────────────────────────────────

interface VoiceWidgetProps {
  /** Corner placement of the floating button. */
  position?: WidgetPosition;
}

// ── Component ──────────────────────────────────────────

/** Floating voice widget — mic button + expandable transcript panel. */
export default function VoiceWidget({
  position = "bottom-right",
}: VoiceWidgetProps) {
  const {
    voiceState,
    micPermission,
    sttSupported,
    startListening,
    stopListening,
    cancelCurrentQuery,
    clearQuery,
    interimTranscript,
    finalTranscript,
    speak,
    stopSpeaking,
    isSpeaking: voiceIsSpeaking,
    requestMicPermission,
  } = useVoice();

  const {
    voiceEnabled,
    connectionState,
    lastResponse,
    isConnected,
  } = useHiveMind();

  const [expanded, setExpanded] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const [rippleKey, setRippleKey] = useState(0);
  const [showPermissionPrompt, setShowPermissionPrompt] = useState(false);
  const panelTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastAutoOpenedResponseRef = useRef<string | null>(null);
  const widgetRef = useRef<HTMLDivElement>(null);

  // ── Derived state ────────────────────────────────────

  const derivedState: DerivedState =
    !voiceEnabled || connectionState === "disconnected" || !isConnected
      ? "disconnected"
      : voiceState;

  const isMicDisabled =
    derivedState === "disconnected" ||
    derivedState === "processing" ||
    micPermission === "denied" ||
    !sttSupported;

  const canStartNewQuery =
    derivedState !== "disconnected" &&
    micPermission !== "denied" &&
    sttSupported;

  const hasQueryContent =
    Boolean(interimTranscript) ||
    Boolean(finalTranscript) ||
    Boolean(lastResponse);

  // ── Expand / collapse with animation ─────────────────

  const openPanel = useCallback(() => {
    if (panelTimerRef.current) clearTimeout(panelTimerRef.current);
    setShowPanel(true);
    requestAnimationFrame(() => setExpanded(true));
  }, []);

  const closePanel = useCallback(() => {
    setExpanded(false);
    panelTimerRef.current = setTimeout(() => setShowPanel(false), 200);
  }, []);

  const togglePanel = useCallback(() => {
    if (expanded) {
      closePanel();
    } else {
      openPanel();
    }
  }, [expanded, closePanel, openPanel]);

  // ── Keyboard handler ─────────────────────────────────

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        togglePanel();
      } else if (e.key === "Escape" && expanded) {
        e.preventDefault();
        closePanel();
      }
    },
    [expanded, closePanel, togglePanel],
  );

  // ── Mic click handler ────────────────────────────────

  const handleMicClick = useCallback(async () => {
    setRippleKey((k) => k + 1);

    if (isMicDisabled) return;

    if (voiceState === "listening") {
      stopListening();
      return;
    }

    if (micPermission === "prompt") {
      setShowPermissionPrompt(true);
      const result = await requestMicPermission();
      setShowPermissionPrompt(false);
      if (result !== "granted") return;
    }

    if (!expanded) openPanel();
    await startListening();
  }, [
    isMicDisabled,
    voiceState,
    micPermission,
    expanded,
    stopListening,
    requestMicPermission,
    openPanel,
    startListening,
  ]);

  const handleAskNextQuery = useCallback(async () => {
    if (!canStartNewQuery) return;
    cancelCurrentQuery();
    if (!expanded) openPanel();
    await startListening();
  }, [canStartNewQuery, cancelCurrentQuery, expanded, openPanel, startListening]);

  const handleCancelQuery = useCallback(() => {
    cancelCurrentQuery();
  }, [cancelCurrentQuery]);

  const handleClearQuery = useCallback(() => {
    clearQuery();
  }, [clearQuery]);

  // Auto-expand only for a newly received response
  useEffect(() => {
    if (!lastResponse) return;
    if (lastAutoOpenedResponseRef.current === lastResponse) return;
    lastAutoOpenedResponseRef.current = lastResponse;
    if (!expanded) {
      openPanel();
    }
  }, [lastResponse, expanded, openPanel]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (panelTimerRef.current) clearTimeout(panelTimerRef.current);
    };
  }, []);

  // ── Render ─────────────────────────────────────────

  if (!voiceEnabled) {
    return null;
  }

  const micIcon =
    derivedState === "disconnected" || micPermission === "denied" ? (
      <MicOffIcon />
    ) : derivedState === "speaking" ? (
      <SpeakerIcon />
    ) : (
      <MicIcon />
    );

  return (
    <div
      ref={widgetRef}
      className={`fixed z-[900] ${positionClasses(position)}`}
      onKeyDown={handleKeyDown}
      role="region"
      aria-label="Voice assistant"
    >
      {/* ── Expanded panel ──────────────────────── */}
      {showPanel && (
        <div
          className={`absolute ${panelPositionClasses(position)} w-[300px] max-sm:fixed max-sm:inset-x-3 max-sm:bottom-20 max-sm:w-auto ${
            expanded ? "voice-panel-enter" : "voice-panel-exit"
          } rounded-xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur-md dark:border-slate-700 dark:bg-slate-900/95`}
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
              {stateLabel(derivedState)}
            </span>
            <button
              type="button"
              onClick={closePanel}
              className="rounded p-0.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
              aria-label="Minimize voice widget"
            >
              <CloseIcon />
            </button>
          </div>

          {showPermissionPrompt && (
            <p className="mb-2 rounded bg-sky-50 p-2 text-xs text-sky-700 dark:bg-sky-900/30 dark:text-sky-300">
              AVAROS needs microphone access for voice interaction.
            </p>
          )}

          {micPermission === "denied" && (
            <p className="mb-2 rounded bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/30 dark:text-red-400">
              Microphone access denied. Use text mode instead.
            </p>
          )}

          {!sttSupported && derivedState !== "disconnected" && (
            <p className="mb-2 rounded bg-amber-50 p-2 text-xs text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
              Speech recognition is not supported in this browser.
            </p>
          )}

          {derivedState === "disconnected" && (
            <p className="mb-2 rounded bg-slate-100 p-2 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              Voice is unavailable. Check your connection.
            </p>
          )}

          {derivedState !== "disconnected" && micPermission !== "denied" && sttSupported && (
            <TranscriptDisplay
              interimTranscript={interimTranscript}
              finalTranscript={finalTranscript}
              isListening={derivedState === "listening"}
            />
          )}

          {derivedState !== "disconnected" && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => void handleAskNextQuery()}
                disabled={!canStartNewQuery}
                className="rounded bg-sky-100 px-2 py-1 text-[10px] font-medium text-sky-700 transition-colors hover:bg-sky-200 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-sky-900/30 dark:text-sky-300 dark:hover:bg-sky-800/40"
              >
                Ask next
              </button>

              {(derivedState === "listening" || derivedState === "processing") && (
                <button
                  type="button"
                  onClick={handleCancelQuery}
                  className="rounded bg-amber-100 px-2 py-1 text-[10px] font-medium text-amber-700 transition-colors hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:hover:bg-amber-800/40"
                >
                  Cancel query
                </button>
              )}

              {hasQueryContent && (
                <button
                  type="button"
                  onClick={handleClearQuery}
                  className="rounded bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-700 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                >
                  Clear
                </button>
              )}
            </div>
          )}

          <ResponseDisplay
            responseText={lastResponse}
            isSpeaking={voiceIsSpeaking}
            onReplay={(text) => void speak(text)}
            onStopSpeaking={stopSpeaking}
          />
        </div>
      )}

      {/* ── Mic button ──────────────────────────── */}
      <div className="relative">
        <RecordingIndicator voiceState={voiceState} />

        <button
          type="button"
          onClick={() => void handleMicClick()}
          className={`relative flex h-14 w-14 items-center justify-center rounded-full transition-transform duration-150 hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900 ${micColorClasses(derivedState)} ${micAnimationClass(derivedState)}`}
          disabled={isMicDisabled && derivedState !== "disconnected"}
          aria-label={micTooltip(derivedState, micPermission)}
          title={micTooltip(derivedState, micPermission)}
        >
          {derivedState === "processing" ? (
            <span
              className="voice-spinner inline-block h-5 w-5 rounded-full border-2 border-white/30 border-t-white"
              aria-hidden="true"
            />
          ) : (
            micIcon
          )}

          <span
            key={rippleKey}
            className={`voice-ripple ${rippleKey > 0 ? "voice-ripple--active bg-white/30" : ""}`}
          />
        </button>

        {!expanded && (
          <span
            className={`absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-white dark:border-slate-900 ${dotClasses(derivedState)}`}
            aria-hidden="true"
          />
        )}
      </div>
    </div>
  );
}
