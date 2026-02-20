import { useEffect, useRef } from "react";

import type { Message } from "../../hooks/useConversation";

type MessageHistoryProps = {
  messages: Message[];
  isProcessing: boolean;
  canReplay: boolean;
  onReplay: (text: string) => void;
  onClear: () => void;
};

function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function renderSourceIcon(message: Message) {
  if (message.source === "avaros") return "🤖";
  return message.inputMode === "voice" ? "🎤" : "⌨️";
}

export default function MessageHistory({
  messages,
  isProcessing,
  canReplay,
  onReplay,
  onClear,
}: MessageHistoryProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const isEmptyState = messages.length === 0 && !isProcessing;

  useEffect(() => {
    if (!scrollerRef.current) return;
    if (isEmptyState) {
      scrollerRef.current.scrollTop = 0;
      return;
    }
    scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [messages, isProcessing, isEmptyState]);

  const handleClear = () => {
    if (!messages.length) return;
    if (window.confirm("Clear conversation?")) {
      onClear();
    }
  };

  return (
    <section className="voice-chat-history">
      <header className="voice-chat-history__header">
        <p className="voice-chat-history__title">Conversation</p>
        <button
          type="button"
          className="voice-chat-history__clear"
          onClick={handleClear}
          disabled={!messages.length}
          title="Clear conversation"
          aria-label="Clear conversation"
        >
          🗑
        </button>
      </header>

      <div
        className={`voice-chat-history__scroller ${
          isEmptyState ? "voice-chat-history__scroller--empty" : ""
        }`}
        ref={scrollerRef}
        role="log"
        aria-live="polite"
      >
        {!messages.length ? (
          <div className="voice-chat-history__empty">
            <p className="voice-chat-history__empty-icon" aria-hidden="true">💬</p>
            <p>Say &quot;Hey AVAROS&quot; or type a question below.</p>
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
                  <span className="voice-chat-message__source">
                    <span aria-hidden="true">{renderSourceIcon(message)}</span>
                  </span>
                  <time dateTime={message.timestamp.toISOString()}>
                    {formatTimestamp(message.timestamp)}
                  </time>
                  {message.source === "avaros" && (
                    <button
                      type="button"
                      className="voice-chat-message__replay"
                      onClick={() => onReplay(message.text)}
                      disabled={!canReplay}
                      aria-label="Replay response"
                    >
                      🔊
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))
        )}

        {isProcessing && (
          <article className="voice-chat-message voice-chat-message--avaros">
            <div className="voice-chat-message__bubble">
              <div className="voice-chat-typing" aria-label="AVAROS is typing">
                <span />
                <span />
                <span />
              </div>
            </div>
          </article>
        )}
      </div>
    </section>
  );
}
