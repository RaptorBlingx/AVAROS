import { useMemo, useState, type FormEvent } from "react";

type ChatInputProps = {
  isConnected: boolean;
  disabled: boolean;
  onSend: (text: string) => Promise<void> | void;
};

const MAX_CHARS = 500;

export default function ChatInput({
  isConnected,
  disabled,
  onSend,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [sendError, setSendError] = useState("");

  const trimmed = value.trim();
  const remaining = MAX_CHARS - value.length;
  const canSend = trimmed.length > 0 && !disabled && isConnected;
  const showCounter = value.length > 400;

  const hasWarning = Boolean(sendError) || !isConnected;
  const helperText = useMemo(() => {
    if (sendError) return sendError;
    if (!isConnected) return "Not connected. Check voice settings.";
    return "Ask AVAROS something...";
  }, [isConnected, sendError]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSend) return;
    try {
      await onSend(trimmed);
      setValue("");
      setSendError("");
    } catch {
      setSendError("Could not send message. Please try again.");
    }
  };

  return (
    <form className="voice-chat-input" onSubmit={(e) => void handleSubmit(e)}>
      <div className="voice-chat-input__row">
        <input
          type="text"
          value={value}
          onChange={(event) => {
            setValue(event.target.value.slice(0, MAX_CHARS));
            if (sendError) {
              setSendError("");
            }
          }}
          placeholder="Type your message"
          className="voice-chat-input__field"
          readOnly={disabled}
          aria-label="Chat message input"
        />
        <button
          type="submit"
          className="voice-chat-input__send"
          disabled={!canSend}
          aria-label="Send message"
        >
          →
        </button>
      </div>
      <div className="voice-chat-input__meta">
        <span
          className={`voice-chat-input__warning ${
            hasWarning ? "voice-chat-input__warning--error" : ""
          }`}
        >
          {helperText}
        </span>
        {showCounter && (
          <span className="voice-chat-input__counter">{remaining}</span>
        )}
      </div>
    </form>
  );
}
