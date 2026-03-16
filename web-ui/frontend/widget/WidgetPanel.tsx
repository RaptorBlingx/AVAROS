import React, { useEffect, useRef, useState } from "react";

import type {
  ChatMessage,
  WidgetConnectionState,
  WidgetMode,
  WidgetVisualState,
} from "./types";

type WidgetPanelProps = {
  mode: WidgetMode;
  disabledModes: WidgetMode[];
  messages: ChatMessage[];
  connectionState: WidgetConnectionState;
  listeningSupported: boolean;
  listeningActive: boolean;
  micError: string | null;
  inputValue: string;
  processing: boolean;
  sendDisabled: boolean;
  visualState: WidgetVisualState;
  onListenToggle: () => void;
  onCancelRequest?: () => void;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onModeChange: (mode: WidgetMode) => void;
  onClear: () => void;
  onStopSpeaking?: () => void;
  brandLogoSrc: string;
};

const MODE_LABEL: Record<WidgetMode, string> = {
  "wake-word": "Wake Word",
  "push-to-talk": "PTT",
  text: "Text",
};

const MODE_ORDER: WidgetMode[] = ["wake-word", "push-to-talk", "text"];

const STATE_LABEL: Record<WidgetVisualState, string> = {
  idle: "Ready",
  listening: "Listening...",
  processing: "Processing...",
  speaking: "Speaking...",
  error: "Voice Error",
  disabled: "Voice unavailable",
};

function getActionLabel(state: WidgetVisualState): string {
  if (state === "listening") return "Stop Listening";
  if (state === "speaking") return "Stop Speaking";
  if (state === "processing") return "Cancel";
  return "Start Listening";
}

function buildStateLabel(
  connectionState: WidgetConnectionState,
  visualState: WidgetVisualState,
): string {
  if (connectionState === "error") return "Voice unavailable";
  if (connectionState === "connecting") return "Connecting...";
  if (connectionState === "disconnected") return "Disconnected";
  return STATE_LABEL[visualState];
}

function buildModeHint(mode: WidgetMode): string {
  if (mode === "wake-word") return "Say 'Hey Avaros' to activate.";
  if (mode === "push-to-talk") return "Press the mic button when speaking.";
  return "Keyboard mode. Audio capture is stopped.";
}

function renderStateIcon(state: WidgetVisualState): React.ReactNode {
  if (state === "processing") {
    return (
      <span
        className="voice-widget__icon voice-widget__icon--cancel"
        aria-hidden="true"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </span>
    );
  }
  if (state === "speaking") {
    return (
      <span className="voice-widget__icon" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 10v4h4l5 4V6l-5 4H4z" />
          <path d="M17 9a4 4 0 010 6" />
          <path d="M20 7a7 7 0 010 10" />
        </svg>
      </span>
    );
  }
  return (
    <span className="voice-widget__icon" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M6 11a6 6 0 0012 0M12 17v4M8.5 21h7" />
      </svg>
    </span>
  );
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function WidgetPanel({
  mode,
  disabledModes,
  messages,
  connectionState,
  listeningSupported,
  listeningActive,
  micError,
  inputValue,
  processing,
  sendDisabled,
  visualState,
  onListenToggle,
  onCancelRequest,
  onInputChange,
  onSend,
  onModeChange,
  onClear,
  onStopSpeaking,
  brandLogoSrc,
}: WidgetPanelProps) {
  const historyRef = useRef<HTMLDivElement | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  useEffect(() => {
    if (!historyRef.current) return;
    historyRef.current.scrollTop = historyRef.current.scrollHeight;
  }, [messages, processing]);

  const hasConnectionError = connectionState === "error";
  const isConnecting = connectionState === "connecting";
  const isDisconnected = connectionState === "disconnected";
  const helperText = hasConnectionError
    ? "Not connected. Check voice settings."
    : isConnecting
    ? "Connecting to HiveMind..."
    : isDisconnected
    ? "Disconnected. Reopen widget or retry shortly."
    : "Ask AVAROS something...";
  const showCounter = inputValue.length > 400;
  const remaining = Math.max(0, 500 - inputValue.length);
  const stateLabel = buildStateLabel(connectionState, visualState);
  const isDisabled =
    visualState === "disabled" ||
    connectionState === "error" ||
    connectionState === "disconnected";

  const handlePrimaryAction = () => {
    if (visualState === "listening") {
      onListenToggle();
      return;
    }
    if (visualState === "processing" && onCancelRequest) {
      onCancelRequest();
      return;
    }
    if (visualState === "speaking") {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      onStopSpeaking?.();
      return;
    }
    onListenToggle();
  };

  const handleClearClick = () => {
    if (!messages.length) return;
    setShowClearConfirm(true);
  };

  const handleConfirmClear = () => {
    onClear();
    setShowClearConfirm(false);
  };

  useEffect(() => {
    if (!showClearConfirm) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowClearConfirm(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showClearConfirm]);

  return (
    <section
      className="voice-widget__panel aw-widget-panel"
      aria-label="AVAROS panel"
    >
      <header className="voice-widget__header">
        <div className="voice-widget__header-row">
          <img
            src={brandLogoSrc}
            alt="AVAROS"
            className="voice-widget__header-logo"
          />
          <div className="voice-widget__header-left">
            <p className="voice-widget__title">Voice Assistant</p>
            <p className="voice-widget__state" aria-live="polite">
              {stateLabel}
            </p>
          </div>
        </div>
        {mode !== "text" && (
          <button
            type="button"
            className={`voice-widget__header-action voice-widget__header-action--${
              visualState === "disabled" ? "disconnected" : visualState
            }`}
            onClick={handlePrimaryAction}
            disabled={isDisabled}
            title={
              visualState === "processing"
                ? "Cancel current request"
                : getActionLabel(visualState)
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

      {hasConnectionError ? (
        <p className="voice-widget__error">
          Voice unavailable. HiveMind is not connected.
        </p>
      ) : null}
      {micError ? <p className="voice-widget__error">{micError}</p> : null}

      <div className="voice-chat-panel">
        <div className="voice-chat-controls">
          <div className="voice-chat-toggle-wrap">
            <div
              className="voice-chat-toggle"
              role="tablist"
              aria-label="Voice mode"
            >
              {MODE_ORDER.map((candidate) => {
                const disabled = disabledModes.includes(candidate);
                return (
                  <button
                    key={candidate}
                    type="button"
                    role="tab"
                    aria-selected={mode === candidate}
                    disabled={disabled}
                    className={`voice-chat-toggle__button ${
                      mode === candidate
                        ? "voice-chat-toggle__button--active"
                        : ""
                    }`}
                    onClick={() => onModeChange(candidate)}
                    title={
                      disabled ? "Disabled by host" : MODE_LABEL[candidate]
                    }
                  >
                    {MODE_LABEL[candidate]}
                  </button>
                );
              })}
            </div>
            <p className="voice-chat-toggle__hint">{buildModeHint(mode)}</p>
          </div>
        </div>

        <div className="voice-chat-history">
          <header className="voice-chat-history__header">
            <p className="voice-chat-history__title">Conversation</p>
            <button
              type="button"
              className="voice-chat-history__clear"
              onClick={handleClearClick}
              disabled={!messages.length}
              title="Clear conversation"
              aria-label="Clear conversation"
            >
              🗑
            </button>
          </header>

          <div
            ref={historyRef}
            className={`voice-chat-history__scroller ${
              messages.length === 0 ? "voice-chat-history__scroller--empty" : ""
            }`}
            role="log"
            aria-live="polite"
          >
            {showClearConfirm && (
              <div
                className="voice-chat-confirm-overlay"
                role="dialog"
                aria-modal="true"
                aria-labelledby="widget-clear-confirm-title"
                aria-describedby="widget-clear-confirm-desc"
              >
                <div
                  className="voice-chat-confirm-backdrop"
                  onClick={() => setShowClearConfirm(false)}
                  aria-hidden="true"
                />
                <div className="voice-chat-confirm-dialog">
                  <h3
                    id="widget-clear-confirm-title"
                    className="voice-chat-confirm-title"
                  >
                    Clear conversation?
                  </h3>
                  <p
                    id="widget-clear-confirm-desc"
                    className="voice-chat-confirm-desc"
                  >
                    All messages in this chat will be removed. This cannot be
                    undone.
                  </p>
                  <div className="voice-chat-confirm-actions">
                    <button
                      type="button"
                      className="voice-chat-confirm-btn voice-chat-confirm-btn--cancel"
                      onClick={() => setShowClearConfirm(false)}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="voice-chat-confirm-btn voice-chat-confirm-btn--clear"
                      onClick={handleConfirmClear}
                    >
                      Clear
                    </button>
                  </div>
                </div>
              </div>
            )}
            {messages.length === 0 ? (
              <div className="voice-chat-history__empty">
                <p
                  className="voice-chat-history__empty-icon"
                  aria-hidden="true"
                >
                  💬
                </p>
                <p>Say &quot;Hey Avaros&quot; or type a question below.</p>
              </div>
            ) : (
              messages.map((message) => (
                <article
                  key={message.id}
                  className={`voice-chat-message voice-chat-message--${message.source}`}
                >
                  <div className="voice-chat-message__bubble">
                    <p className="voice-chat-message__text">{message.text}</p>
                    <div className="voice-chat-message__meta">
                      <span
                        className="voice-chat-message__source"
                        aria-hidden="true"
                      >
                        {message.source === "user" ? "⌨️" : "🤖"}
                      </span>
                      <time dateTime={message.timestamp.toISOString()}>
                        {formatTime(message.timestamp)}
                      </time>
                    </div>
                  </div>
                </article>
              ))
            )}

            {processing ? (
              <article className="voice-chat-message voice-chat-message--avaros">
                <div className="voice-chat-message__bubble">
                  <div
                    className="voice-chat-typing"
                    aria-label="AVAROS is thinking"
                  >
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </article>
            ) : null}
          </div>
        </div>

        <form
          className="voice-chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            onSend();
          }}
        >
          <div className="voice-chat-input__row">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder="Type your message"
              className="voice-chat-input__field"
              maxLength={500}
            />
            <button
              type="submit"
              className="voice-chat-input__send"
              disabled={sendDisabled}
              aria-label="Send message"
            >
              →
            </button>
          </div>
          <div className="voice-chat-input__meta">
            <span
              className={`voice-chat-input__warning ${
                hasConnectionError ? "voice-chat-input__warning--error" : ""
              }`}
            >
              {helperText}
            </span>
            {showCounter ? (
              <span className="voice-chat-input__counter">{remaining}</span>
            ) : null}
          </div>
        </form>
      </div>
    </section>
  );
}
