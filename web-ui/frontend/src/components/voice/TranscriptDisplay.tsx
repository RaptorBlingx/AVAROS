import { useEffect, useRef } from "react";

type TranscriptDisplayProps = {
  interimTranscript: string;
  finalTranscript: string;
  listening: boolean;
};

export default function TranscriptDisplay({
  interimTranscript,
  finalTranscript,
  listening,
}: TranscriptDisplayProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!scrollerRef.current) {
      return;
    }
    scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [finalTranscript, interimTranscript]);

  const hasTranscript = finalTranscript.trim().length > 0 || interimTranscript.trim().length > 0;

  return (
    <section className="voice-widget__section" aria-live="polite">
      <p className="voice-widget__section-title">Transcript</p>
      <div ref={scrollerRef} className="voice-transcript" role="log" aria-atomic="false">
        {!hasTranscript ? (
          <p className="voice-transcript__placeholder">
            {listening ? "Listening..." : "Start speaking to see live transcript."}
          </p>
        ) : (
          <>
            {finalTranscript.trim().length > 0 && (
              <p className="voice-transcript__final">{finalTranscript}</p>
            )}
            {interimTranscript.trim().length > 0 && (
              <p className="voice-transcript__interim">{interimTranscript}</p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
