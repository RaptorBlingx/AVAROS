import { useCallback, useEffect, useRef, useState } from "react";

import { useVoice } from "../../contexts/VoiceContext";

type TestStatus = {
  tone: "neutral" | "success" | "warning" | "error";
  message: string;
};

function getMeterTone(level: number): string {
  if (level >= 0.85) return "bg-rose-500";
  if (level < 0.12) return "bg-amber-400";
  return "bg-emerald-500";
}

export default function MicrophoneTest() {
  const { requestMicPermission } = useVoice();
  const [isTesting, setIsTesting] = useState(false);
  const [level, setLevel] = useState(0);
  const [status, setStatus] = useState<TestStatus>({
    tone: "neutral",
    message: "Run a quick microphone test to verify input quality.",
  });

  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const hasSignalRef = useRef(false);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (contextRef.current) {
      void contextRef.current.close();
      contextRef.current = null;
    }
    analyserRef.current = null;
  }, []);

  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  const stopWithStatus = useCallback(
    (nextStatus: TestStatus) => {
      cleanup();
      setIsTesting(false);
      setLevel(0);
      setStatus(nextStatus);
    },
    [cleanup],
  );

  const runMeterLoop = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const samples = new Uint8Array(analyser.fftSize);
    const update = () => {
      if (!analyserRef.current) return;
      analyser.getByteTimeDomainData(samples);

      let sum = 0;
      for (let i = 0; i < samples.length; i += 1) {
        const centered = (samples[i] - 128) / 128;
        sum += centered * centered;
      }
      const rms = Math.sqrt(sum / samples.length);
      const normalized = Math.max(0, Math.min(1, rms * 3));
      if (normalized > 0.05) {
        hasSignalRef.current = true;
      }
      setLevel(normalized);
      rafRef.current = window.requestAnimationFrame(update);
    };

    rafRef.current = window.requestAnimationFrame(update);
  }, []);

  const handleRunTest = useCallback(async () => {
    if (isTesting) return;
    setStatus({ tone: "neutral", message: "Listening for microphone input..." });
    setIsTesting(true);
    setLevel(0);
    hasSignalRef.current = false;

    try {
      const permission = await requestMicPermission();
      if (permission !== "granted") {
        stopWithStatus({
          tone: "error",
          message:
            "Permission denied. Enable microphone access in browser settings.",
        });
        return;
      }

      if (!navigator.mediaDevices?.getUserMedia) {
        stopWithStatus({
          tone: "error",
          message: "Microphone not detected on this browser/device.",
        });
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (stream.getAudioTracks().length === 0) {
        stopWithStatus({
          tone: "error",
          message: "Microphone not detected. Connect a valid input device.",
        });
        return;
      }
      streamRef.current = stream;

      const AudioContextCtor =
        window.AudioContext ||
        (
          window as Window & {
            webkitAudioContext?: typeof AudioContext;
          }
        ).webkitAudioContext;
      if (!AudioContextCtor) {
        stopWithStatus({
          tone: "error",
          message: "AudioContext is unavailable in this browser.",
        });
        return;
      }

      const audioContext = new AudioContextCtor();
      contextRef.current = audioContext;
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      analyserRef.current = analyser;

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      runMeterLoop();

      timeoutRef.current = window.setTimeout(() => {
        if (hasSignalRef.current) {
          stopWithStatus({
            tone: "success",
            message: "Microphone working ✓ Audio signal detected.",
          });
        } else {
          stopWithStatus({
            tone: "warning",
            message:
              "No audio detected. Check input device or move closer to the microphone.",
          });
        }
      }, 5000);
    } catch (error) {
      const err = error as DOMException | Error;
      if ("name" in err && err.name === "NotFoundError") {
        stopWithStatus({
          tone: "error",
          message: "Microphone not detected. Please connect an input device.",
        });
        return;
      }
      stopWithStatus({
        tone: "error",
        message: "Microphone test failed. Please retry.",
      });
    }
  }, [isTesting, requestMicPermission, runMeterLoop, stopWithStatus]);

  const statusClasses =
    status.tone === "success"
      ? "text-emerald-700 dark:text-emerald-300"
      : status.tone === "warning"
        ? "text-amber-700 dark:text-amber-300"
        : status.tone === "error"
          ? "text-rose-700 dark:text-rose-300"
          : "text-slate-600 dark:text-slate-300";

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-slate-700 dark:bg-slate-900/40">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
            Microphone Test
          </p>
          <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
            Captures input for 5 seconds and checks signal quality.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleRunTest()}
          disabled={isTesting}
          className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isTesting ? "Testing..." : "Test Microphone"}
        </button>
      </div>

      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className={`h-full transition-[width] duration-100 ${getMeterTone(level)}`}
          style={{ width: `${Math.round(level * 100)}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
        <span>Too quiet</span>
        <span>Good level</span>
        <span>Clipping</span>
      </div>

      <p className={`m-0 text-xs ${statusClasses}`}>{status.message}</p>
    </div>
  );
}
