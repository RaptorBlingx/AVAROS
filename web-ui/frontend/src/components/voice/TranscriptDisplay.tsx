/**
 * TranscriptDisplay — shows interim and final speech-to-text results.
 *
 * Interim text is shown in grey (updating as user speaks).
 * Final text is shown in full contrast once recognition completes.
 * Auto-scrolls to the bottom as text appears.
 */

import { useEffect, useRef } from "react";

interface TranscriptDisplayProps {
  /** Interim (partial) transcript that updates while speaking. */
  interimTranscript: string;
  /** Final (confirmed) transcript after speech ends. */
  finalTranscript: string;
  /** Whether the system is currently in listening state. */
  isListening: boolean;
}

/** Live transcript area in the expanded voice widget panel. */
export default function TranscriptDisplay({
  interimTranscript,
  finalTranscript,
  isListening,
}: TranscriptDisplayProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [interimTranscript, finalTranscript]);

  const hasContent = interimTranscript || finalTranscript;

  return (
    <div
      ref={scrollRef}
      className="max-h-[3.75rem] overflow-y-auto text-xs leading-relaxed"
      aria-live="polite"
      aria-atomic="false"
    >
      {hasContent ? (
        <p className="m-0">
          {finalTranscript && (
            <span className="text-slate-800 dark:text-slate-100">
              {finalTranscript}
            </span>
          )}
          {interimTranscript && (
            <span className="text-slate-400 dark:text-slate-500">
              {finalTranscript ? " " : ""}
              {interimTranscript}
            </span>
          )}
        </p>
      ) : (
        <p className="m-0 italic text-slate-400 dark:text-slate-500">
          {isListening ? "Listening…" : "Click the mic to speak"}
        </p>
      )}
    </div>
  );
}
