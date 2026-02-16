/**
 * RecordingIndicator — animated concentric rings around the mic button.
 *
 * Shown during the "listening" state to provide visual feedback that
 * the microphone is active. CSS-only animation (no canvas).
 */

import type { VoiceState } from "../../contexts/voice-types";

interface RecordingIndicatorProps {
  /** Current voice interaction state. */
  voiceState: VoiceState;
}

/** Animated rings that expand outward from the mic button while listening. */
export default function RecordingIndicator({
  voiceState,
}: RecordingIndicatorProps) {
  if (voiceState !== "listening") {
    return null;
  }

  return (
    <>
      <span className="voice-ring voice-ring--1" aria-hidden="true" />
      <span className="voice-ring voice-ring--2" aria-hidden="true" />
      <span className="voice-ring voice-ring--3" aria-hidden="true" />
    </>
  );
}
