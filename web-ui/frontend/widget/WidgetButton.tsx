import type { WidgetConnectionState, WidgetSize, WidgetVisualState } from "./types";

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
  medium: 56,
  large: 72,
};

const CONNECTION_CLASS: Record<WidgetConnectionState, string> = {
  connected: "aw-connection-dot--connected",
  connecting: "aw-connection-dot--connecting",
  disconnected: "aw-connection-dot--disconnected",
  error: "aw-connection-dot--disconnected",
};

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
      <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M6 11a6 6 0 0012 0M12 17v4M8.5 21h7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      {state === "disabled" ? (
        <path d="M4 4l16 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
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
  return (
    <button
      type="button"
      className={`voice-widget__button ${mapVisualClass(visualState)}`}
      style={{ width: SIZE_TO_PX[size], height: SIZE_TO_PX[size] }}
      onClick={onClick}
      title={tooltip}
      aria-label={open ? "Close AVAROS widget" : "Open AVAROS widget"}
    >
      <span className="voice-widget__icon" aria-hidden="true">
        {renderIcon(visualState)}
      </span>
      <span className={`aw-connection-dot ${CONNECTION_CLASS[connectionState]}`} />
      {label ? <span className="aw-widget-label">{label}</span> : null}
    </button>
  );
}
