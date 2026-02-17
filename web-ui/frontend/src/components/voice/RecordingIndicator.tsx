import type { CSSProperties } from "react";

type RecordingIndicatorProps = {
  active: boolean;
  variant: "listening" | "speaking";
};

export default function RecordingIndicator({ active, variant }: RecordingIndicatorProps) {
  if (!active) {
    return null;
  }

  return (
    <span
      className={`voice-recording-indicator voice-recording-indicator--${variant}`}
      aria-hidden="true"
    >
      <span className="voice-recording-indicator__ring voice-recording-indicator__ring--one" />
      <span className="voice-recording-indicator__ring voice-recording-indicator__ring--two" />
      <span className="voice-recording-indicator__ring voice-recording-indicator__ring--three" />
      <span className="voice-recording-indicator__bars">
        {[0, 1, 2, 3, 4].map((bar) => (
          <span
            key={bar}
            className="voice-recording-indicator__bar"
            style={{ "--voice-bar-delay": `${bar * 90}ms` } as CSSProperties}
          />
        ))}
      </span>
    </span>
  );
}
