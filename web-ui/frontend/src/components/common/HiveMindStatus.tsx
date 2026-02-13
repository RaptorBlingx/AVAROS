/**
 * HiveMind connection status indicator for the Sidebar.
 *
 * Shows a colored dot with label reflecting the WebSocket state:
 *   - Green: Connected
 *   - Yellow: Connecting
 *   - Red: Disconnected / Error
 *
 * Only renders when voice is enabled in backend config.
 */

import { useCallback, useState } from "react";

import { useHiveMind } from "../../contexts/HiveMindContext";
import { useTheme } from "./ThemeProvider";

const STATE_CONFIG = {
  connected: {
    dot: "bg-emerald-400",
    label: "Voice Connected",
    pulse: false,
  },
  connecting: {
    dot: "bg-amber-400",
    label: "Connecting...",
    pulse: true,
  },
  disconnected: {
    dot: "bg-slate-400",
    label: "Voice Offline",
    pulse: false,
  },
  error: {
    dot: "bg-red-400",
    label: "Connection Error",
    pulse: false,
  },
} as const;

export default function HiveMindStatus() {
  const {
    connectionState,
    voiceEnabled,
    connect,
    disconnect,
    isConnected,
    connectionDetails,
    isSpeaking,
    isProcessing,
  } =
    useHiveMind();
  const { isDark } = useTheme();
  const [showDetails, setShowDetails] = useState(false);

  const handleToggle = useCallback(async () => {
    if (isConnected) {
      disconnect();
    } else {
      try {
        await connect();
      } catch {
        // state change handled by context
      }
    }
  }, [isConnected, connect, disconnect]);

  if (!voiceEnabled) return null;

  const config = STATE_CONFIG[connectionState];

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setShowDetails((prev) => !prev)}
        className={`inline-flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
          isDark
            ? "bg-slate-800/85 text-slate-100 hover:bg-slate-700/90"
            : "bg-white/85 text-slate-700 hover:bg-white"
        }`}
        aria-label={`Voice status: ${config.label}`}
      >
        <span className="relative flex h-3 w-3">
          {config.pulse && (
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${config.dot}`}
            />
          )}
          <span
            className={`relative inline-flex h-3 w-3 rounded-full ${config.dot}`}
          />
        </span>
        <span className="truncate">{config.label}</span>
      </button>

      {showDetails && (
        <div
          className={`absolute bottom-full left-0 mb-2 w-full rounded-lg border p-3 text-xs shadow-lg ${
            isDark
              ? "border-slate-700 bg-slate-900 text-slate-200"
              : "border-slate-200 bg-white text-slate-700"
          }`}
        >
          <p className="mb-1 font-medium">HiveMind Voice</p>
          <p className="mb-2">
            Status:{" "}
            <span className="font-mono">{connectionState}</span>
          </p>
          <p className="mb-1 truncate">
            URL:{" "}
            <span className="font-mono">{connectionDetails.url || "--"}</span>
          </p>
          <p className="mb-1">
            Latency:{" "}
            <span className="font-mono">
              {connectionDetails.latencyMs === null
                ? "--"
                : `${connectionDetails.latencyMs} ms`}
            </span>
          </p>
          <p className="mb-2">
            Session ID:{" "}
            <span className="font-mono">
              {connectionDetails.sessionId ?? "--"}
            </span>
          </p>
          <p className="mb-2">
            {isProcessing ? "Processing" : "Idle"}
            {" · "}
            {isSpeaking ? "Speaking" : "Not speaking"}
          </p>
          <button
            type="button"
            onClick={() => void handleToggle()}
            className={`w-full rounded px-2 py-1 text-xs font-medium transition ${
              isConnected
                ? isDark
                  ? "bg-red-900/50 text-red-300 hover:bg-red-800/60"
                  : "bg-red-100 text-red-700 hover:bg-red-200"
                : isDark
                  ? "bg-emerald-900/50 text-emerald-300 hover:bg-emerald-800/60"
                  : "bg-emerald-100 text-emerald-700 hover:bg-emerald-200"
            }`}
          >
            {isConnected ? "Disconnect" : "Connect"}
          </button>
        </div>
      )}
    </div>
  );
}
