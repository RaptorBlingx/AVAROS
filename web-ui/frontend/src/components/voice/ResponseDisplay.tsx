function formatTimestamp(value: Date | null): string {
  if (!value) {
    return "";
  }
  return value.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

type ResponseDisplayProps = {
  responseText: string | null;
  isSpeaking: boolean;
  receivedAt: Date | null;
  canReplay: boolean;
  onReplay: () => void;
};

export default function ResponseDisplay({
  responseText,
  isSpeaking,
  receivedAt,
  canReplay,
  onReplay,
}: ResponseDisplayProps) {
  const hasResponse = Boolean(responseText && responseText.trim().length > 0);

  return (
    <section className="voice-widget__section" aria-live="polite">
      <p className="voice-widget__section-title">AVAROS Response</p>
      <div className="voice-response">
        {hasResponse ? (
          <>
            <p className="voice-response__text">{responseText}</p>
            <div className="voice-response__meta">
              <span className="voice-response__timestamp">{formatTimestamp(receivedAt)}</span>
              <button
                type="button"
                className="voice-response__replay"
                onClick={onReplay}
                disabled={!canReplay}
                aria-label="Replay AVAROS response"
              >
                <span
                  className={`voice-response__speaker ${isSpeaking ? "voice-response__speaker--active" : ""}`}
                  aria-hidden="true"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M4 10v4h4l5 4V6l-5 4H4z" strokeWidth="1.8" strokeLinejoin="round" />
                    <path d="M17 9a4 4 0 010 6" strokeWidth="1.8" strokeLinecap="round" />
                    <path d="M19.8 6.5a7.5 7.5 0 010 11" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </span>
                {isSpeaking ? "Playing..." : "Replay"}
              </button>
            </div>
          </>
        ) : (
          <p className="voice-response__placeholder">Waiting for AVAROS response...</p>
        )}
      </div>
    </section>
  );
}
