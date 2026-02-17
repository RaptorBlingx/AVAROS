import type { ReactNode } from "react";

export type WidgetPosition =
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left";

export type WidgetVisualState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "error"
  | "disconnected";

export const MICROPHONE_HELP_URL = "https://support.google.com/chrome/answer/2693767";

export const POSITION_CLASS: Record<WidgetPosition, string> = {
  "bottom-right": "voice-widget--bottom-right",
  "bottom-left": "voice-widget--bottom-left",
  "top-right": "voice-widget--top-right",
  "top-left": "voice-widget--top-left",
};

export const STATE_META: Record<WidgetVisualState, { label: string; hint: string }> = {
  idle: {
    label: "Ready",
    hint: "Click microphone to start voice interaction.",
  },
  listening: {
    label: "Listening...",
    hint: "Speak now. AVAROS is capturing your utterance.",
  },
  processing: {
    label: "Processing...",
    hint: "AVAROS is processing your request.",
  },
  speaking: {
    label: "Speaking...",
    hint: "AVAROS is reading the response aloud.",
  },
  error: {
    label: "Voice Error",
    hint: "Voice interaction failed. Try again.",
  },
  disconnected: {
    label: "Voice unavailable",
    hint: "HiveMind is disconnected. Voice interaction is unavailable.",
  },
};

export function deriveVisualState(params: {
  isConnected: boolean;
  voiceEnabled: boolean;
  voiceState: "idle" | "listening" | "processing" | "speaking" | "error";
  isHiveSpeaking: boolean;
  isHiveProcessing: boolean;
  localError: string;
}): WidgetVisualState {
  const {
    isConnected,
    voiceEnabled,
    voiceState,
    isHiveSpeaking,
    isHiveProcessing,
    localError,
  } = params;

  if (!voiceEnabled || !isConnected) return "disconnected";
  if (voiceState === "error" || localError.length > 0) return "error";
  if (voiceState === "speaking" || isHiveSpeaking) return "speaking";
  if (voiceState === "processing" || isHiveProcessing) return "processing";
  if (voiceState === "listening") return "listening";
  return "idle";
}

export function getActionLabel(state: WidgetVisualState): string {
  if (state === "listening") return "Stop Listening";
  if (state === "speaking") return "Stop Speaking";
  if (state === "processing") return "Processing...";
  return "Start Listening";
}

export function renderStateIcon(state: WidgetVisualState): ReactNode {
  if (state === "processing") {
    return <span className="voice-widget__spinner" aria-hidden="true" />;
  }

  if (state === "speaking") {
    return (
      <span className="voice-widget__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M4 10v4h4l5 4V6l-5 4H4z" strokeWidth="1.8" strokeLinejoin="round" />
          <path d="M17 9a4 4 0 010 6" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M20 7a7 7 0 010 10" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </span>
    );
  }

  const withSlash = state === "disconnected";
  return (
    <span className="voice-widget__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <rect x="9" y="3" width="6" height="11" rx="3" strokeWidth="1.8" />
        <path d="M6 11a6 6 0 0012 0M12 17v4M8.5 21h7" strokeWidth="1.8" strokeLinecap="round" />
        {withSlash && <path d="M4 4l16 16" strokeWidth="2" strokeLinecap="round" />}
      </svg>
    </span>
  );
}

export function isLikelyIncompleteUtterance(raw: string): boolean {
  const text = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (!text) return true;

  const exactIncomplete = new Set([
    "what if",
    "show",
    "show me",
    "what is",
    "what's",
    "check",
  ]);
  if (exactIncomplete.has(text)) return true;

  // What-if scenarios require a change amount (digit or number-word).
  const hasAmount = /\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/.test(
    text,
  );
  if (text.startsWith("what if") && !hasAmount) {
    return true;
  }

  return false;
}
