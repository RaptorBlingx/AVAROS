import { useEffect, useRef } from "react";

import type { ChatMessage, WidgetConnectionState, WidgetMode } from "./types";

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
  onListenToggle: () => void;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onModeChange: (mode: WidgetMode) => void;
  brandLogoSrc: string;
};

const MODE_LABEL: Record<WidgetMode, string> = {
  "wake-word": "Wake Word",
  "push-to-talk": "Push-to-Talk",
  text: "Text",
};

const MODE_ORDER: WidgetMode[] = ["wake-word", "push-to-talk", "text"];
const MODE_ICON: Record<WidgetMode, string> = {
  "wake-word": "🎤",
  "push-to-talk": "🔘",
  text: "⌨️",
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function buildStateLabel(
  mode: WidgetMode,
  processing: boolean,
  connectionState: WidgetConnectionState,
  listeningActive: boolean,
): string {
  if (connectionState === "error") {
    return "Voice unavailable";
  }
  if (connectionState === "connecting") {
    return "Connecting...";
  }
  if (connectionState === "disconnected") {
    return "Disconnected";
  }
  if (processing) {
    return "Processing...";
  }
  if (listeningActive) {
    return "Listening...";
  }
  if (mode === "wake-word") {
    return "Wake Word ready";
  }
  if (mode === "push-to-talk") {
    return "Push-to-Talk";
  }
  return "Text mode";
}

function buildModeHint(mode: WidgetMode): string {
  if (mode === "wake-word") {
    return "Say 'Hey AVAROS' to activate.";
  }
  if (mode === "push-to-talk") {
    return "Press the mic button when speaking.";
  }
  return "Keyboard mode. Audio capture is stopped.";
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
  onListenToggle,
  onInputChange,
  onSend,
  onModeChange,
  brandLogoSrc,
}: WidgetPanelProps) {
  const historyRef = useRef<HTMLDivElement | null>(null);

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
        ? "Connection lost. Retrying..."
      : "Ask AVAROS something...";
  const showCounter = inputValue.length > 400;
  const remaining = Math.max(0, 500 - inputValue.length);

  return (
    <section className="voice-widget__panel aw-widget-panel" aria-label="AVAROS panel">
      <header className="voice-widget__header">
        <div>
          <p className="voice-widget__title">Voice Assistant</p>
          <p className="voice-widget__state">
            {buildStateLabel(mode, processing, connectionState, listeningActive)}
          </p>
        </div>
      </header>

      {hasConnectionError ? (
        <p className="voice-widget__error">
          Voice unavailable. HiveMind is not connected.
        </p>
      ) : null}
      {micError ? <p className="voice-widget__error">{micError}</p> : null}

      <div className="voice-chat-panel">
        <div className="voice-chat-toggle-wrap">
          <div className="voice-chat-toggle" role="tablist" aria-label="Widget mode">
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
                    mode === candidate ? "voice-chat-toggle__button--active" : ""
                  }`}
                  onClick={() => onModeChange(candidate)}
                  title={disabled ? "Disabled by host page configuration" : MODE_LABEL[candidate]}
                >
                  <span aria-hidden="true">{MODE_ICON[candidate]}</span>
                  <span>{MODE_LABEL[candidate]}</span>
                </button>
              );
            })}
          </div>
          <p className="voice-chat-toggle__hint">{buildModeHint(mode)}</p>
        </div>

        <div className="voice-widget__actions">
          <button
            type="button"
            className="voice-widget__action"
            onClick={onListenToggle}
            disabled={!listeningSupported}
          >
            {listeningActive ? "Stop Listening" : "Start Listening"}
          </button>
        </div>

        <div className="voice-chat-history">
          <header className="voice-chat-history__header">
            <h4 className="voice-chat-history__title">Conversation</h4>
          </header>

          <div
            ref={historyRef}
            className={`voice-chat-history__scroller ${
              messages.length === 0 ? "voice-chat-history__scroller--empty" : ""
            }`}
            role="log"
            aria-live="polite"
          >
            {messages.length === 0 ? (
              <div className="voice-chat-history__empty">
                <p className="voice-chat-history__empty-icon" aria-hidden="true">
                  💬
                </p>
                <p>Say "Hey AVAROS" or type a question below.</p>
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
                      <span className="voice-chat-message__source" aria-hidden="true">
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
                  <div className="voice-chat-typing" aria-label="AVAROS is thinking">
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
          onSubmit={(event) => {
            event.preventDefault();
            onSend();
          }}
        >
          <div className="voice-chat-input__row">
            <input
              type="text"
              value={inputValue}
              onChange={(event) => onInputChange(event.target.value)}
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

      <footer className="aw-widget-panel__footer">
        <a
          className="aw-widget-panel__brand"
          href="https://avaros.ai"
          target="_blank"
          rel="noreferrer"
          aria-label="Powered by AVAROS"
        >
          <img className="aw-widget-panel__brand-logo" src={brandLogoSrc} alt="AVAROS" />
        </a>
      </footer>
    </section>
  );
}
