import { useState } from "react";

import type { VoiceMode } from "../../contexts/voice-types";
import { useVoice } from "../../contexts/VoiceContext";

type ModeMeta = {
  mode: VoiceMode;
  label: string;
  tooltip: string;
};

const MODES: ModeMeta[] = [
  {
    mode: "wake-word",
    label: "Wake Word",
    tooltip: "Hands-free. Say your configured wake word to start.",
  },
  {
    mode: "push-to-talk",
    label: "PTT",
    tooltip: "Press mic button when speaking.",
  },
  {
    mode: "text",
    label: "Text",
    tooltip: "Keyboard mode. Audio capture is stopped.",
  },
];

export default function ModeToggle() {
  const {
    voiceMode,
    setVoiceMode,
    stopListening,
    stopSpeaking,
    wakeWordState,
    isModelLoading,
    micPermission,
    requestMicPermission,
  } = useVoice();
  const selectedMode = MODES.find((item) => item.mode === voiceMode) ?? MODES[0];
  const wakeWordUnsupported = wakeWordState === "unsupported";
  const wakeWordError = wakeWordState === "error";
  const isWakeWordMode = voiceMode === "wake-word";
  const [modeError, setModeError] = useState("");

  const handleSelect = async (mode: VoiceMode) => {
    const allowWakeWordRetry =
      mode === "wake-word" &&
      mode === voiceMode &&
      (wakeWordError || wakeWordUnsupported || Boolean(modeError));
    if (mode === voiceMode && !allowWakeWordRetry) return;
    if (mode !== "wake-word") {
      stopListening();
      stopSpeaking();
    }
    try {
      if (mode === "wake-word" && micPermission !== "granted") {
        const permission = await requestMicPermission();
        if (permission !== "granted") {
          setModeError(
            "Microphone permission is required for Wake Word. Allow mic access in browser settings.",
          );
          return;
        }
      }
      await setVoiceMode(mode);
      setModeError("");
    } catch {
      setModeError(
        mode === "wake-word"
          ? "Wake Word failed to start. Check microphone permission and use localhost/HTTPS."
          : "Could not switch mode. Please try again.",
      );
    }
  };

  let hintText = selectedMode.tooltip;
  let hintWarning = false;
  if (modeError) {
    hintText = modeError;
    hintWarning = true;
  } else if (isModelLoading && isWakeWordMode) {
    hintText = "Loading wake-word model...";
  } else if (wakeWordUnsupported && isWakeWordMode) {
    hintText = "Wake Word is unavailable in this browser. Use Push-to-Talk.";
    hintWarning = true;
  } else if (wakeWordError && isWakeWordMode) {
    hintText =
      "Wake Word failed to start. Check microphone permission and reload page.";
    hintWarning = true;
  }

  return (
    <div className="voice-chat-toggle-wrap">
      <div className="voice-chat-toggle" role="tablist" aria-label="Voice mode">
        {MODES.map((item) => (
          <button
            key={item.mode}
            type="button"
            role="tab"
            aria-selected={voiceMode === item.mode}
            title={item.tooltip}
            className={`voice-chat-toggle__button ${
              voiceMode === item.mode ? "voice-chat-toggle__button--active" : ""
            }`}
            onClick={() => {
              void handleSelect(item.mode);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p
        className={`voice-chat-toggle__hint ${
          hintWarning ? "voice-chat-toggle__hint--warning" : ""
        }`}
      >
        {hintText}
      </p>
    </div>
  );
}
