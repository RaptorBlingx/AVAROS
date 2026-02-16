/**
 * ResponseDisplay — shows the AVAROS response in a chat-bubble style.
 *
 * Includes a replay button that re-speaks the last response via TTS
 * and a timestamp for when the response was received.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface ResponseDisplayProps {
  /** The last AVAROS response text. */
  responseText: string | null;
  /** Whether TTS is currently playing audio. */
  isSpeaking: boolean;
  /** Callback to replay the last response via TTS. */
  onReplay: (text: string) => void;
  /** Callback to stop ongoing TTS playback. */
  onStopSpeaking: () => void;
}

/** Formats a Date to a short time string (HH:MM). */
function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Response text area in the expanded voice widget panel. */
export default function ResponseDisplay({
  responseText,
  isSpeaking,
  onReplay,
  onStopSpeaking,
}: ResponseDisplayProps) {
  const [timestamp, setTimestamp] = useState<Date | null>(null);
  const prevResponseRef = useRef<string | null>(null);

  // Update timestamp whenever responseText changes to a new value
  useEffect(() => {
    if (responseText && responseText !== prevResponseRef.current) {
      setTimestamp(new Date());
    }
    prevResponseRef.current = responseText;
  }, [responseText]);

  const handleReplayClick = useCallback(() => {
    if (!responseText) return;
    if (isSpeaking) {
      onStopSpeaking();
    } else {
      onReplay(responseText);
    }
  }, [responseText, isSpeaking, onReplay, onStopSpeaking]);

  const timeLabel = useMemo(
    () => (timestamp ? formatTime(timestamp) : null),
    [timestamp],
  );

  if (!responseText) {
    return null;
  }

  return (
    <div className="mt-2 rounded-lg bg-sky-50 p-2 dark:bg-sky-900/30">
      <p className="m-0 text-xs leading-relaxed text-slate-700 dark:text-slate-200">
        {responseText}
      </p>

      <div className="mt-1 flex items-center justify-between">
        {timeLabel && (
          <span className="text-[10px] text-slate-400 dark:text-slate-500">
            {timeLabel}
          </span>
        )}

        <button
          type="button"
          onClick={handleReplayClick}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-sky-600 transition-colors hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800/40"
          aria-label={isSpeaking ? "Stop speaking" : "Replay response"}
          title={isSpeaking ? "Stop speaking" : "Click to replay"}
        >
          {isSpeaking ? (
            <>
              {/* Speaker animated bars */}
              <span className="flex items-end gap-px" aria-hidden="true">
                <span className="voice-bar voice-bar--1 bg-sky-500" />
                <span className="voice-bar voice-bar--2 bg-sky-500" />
                <span className="voice-bar voice-bar--3 bg-sky-500" />
                <span className="voice-bar voice-bar--4 bg-sky-500" />
              </span>
              Stop
            </>
          ) : (
            <>
              {/* Speaker icon */}
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
              </svg>
              Replay
            </>
          )}
        </button>
      </div>
    </div>
  );
}
