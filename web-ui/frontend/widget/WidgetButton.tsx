import type {
  WidgetConnectionState,
  WidgetSize,
  WidgetVisualState,
} from "./types";

type WidgetButtonProps = {
  visualState: WidgetVisualState;
  connectionState: WidgetConnectionState;
  size: WidgetSize;
  label: string;
  open: boolean;
  onClick: () => void;
  tooltip: string;
};

const SIZE_TO_PX: Record<WidgetSize, number> = {
  small: 40,
  medium: 58,
  large: 72,
};

function RecordingIndicator({
  active,
  variant,
}: {
  active: boolean;
  variant: "listening" | "speaking";
}) {
  if (!active) return null;
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
            style={
              { "--voice-bar-delay": `${bar * 90}ms` } as React.CSSProperties
            }
          />
        ))}
      </span>
    </span>
  );
}

function renderIcon(state: WidgetVisualState) {
  if (state === "processing") {
    return <span className="voice-widget__spinner" aria-hidden="true" />;
  }

  if (state === "speaking") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M4 10v4h4l5 4V6l-5 4H4z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="M17 9a4 4 0 010 6"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect
        x="9"
        y="3"
        width="6"
        height="11"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.8"
      />
      <path
        d="M6 11a6 6 0 0012 0M12 17v4M8.5 21h7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      {state === "disabled" ? (
        <path
          d="M4 4l16 16"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      ) : null}
    </svg>
  );
}

function mapVisualClass(state: WidgetVisualState): string {
  if (state === "disabled") {
    return "voice-widget__button--disconnected aw-widget-button--disabled";
  }
  return `voice-widget__button--${state}`;
}

export function WidgetButton({
  visualState,
  connectionState,
  size,
  label,
  open,
  onClick,
  tooltip,
}: WidgetButtonProps) {
  const showRecordingIndicator =
    visualState === "listening" || visualState === "speaking";
  const recordingVariant =
    visualState === "speaking" ? "speaking" : "listening";
  const dotState =
    visualState === "disabled"
      ? "disconnected"
      : connectionState === "connected"
      ? "connected"
      : connectionState === "error"
      ? "error"
      : "disconnected";

  return (
    <button
      type="button"
      className={`voice-widget__button ${mapVisualClass(visualState)}`}
      style={{ width: SIZE_TO_PX[size], height: SIZE_TO_PX[size] }}
      onClick={onClick}
      title={tooltip}
      aria-label={open ? "Close AVAROS widget" : "Open AVAROS widget"}
    >
      <RecordingIndicator
        active={showRecordingIndicator}
        variant={recordingVariant}
      />
      <span className="voice-widget__icon" aria-hidden="true">
        {renderIcon(visualState)}
      </span>
      <span
        className={`voice-widget__dot voice-widget__dot--${dotState}`}
        aria-hidden="true"
      />
      {label ? <span className="aw-widget-label">{label}</span> : null}
    </button>
  );
}
