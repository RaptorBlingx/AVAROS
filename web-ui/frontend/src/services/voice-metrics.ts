/**
 * Voice pipeline latency measurement service.
 *
 * Records timestamps at key points in the voice interaction pipeline
 * and calculates durations between them. Used by VoiceContext to
 * automatically track:
 *
 *   wake_word_detected → stt_started      (wake word overhead)
 *   stt_started → stt_completed           (transcription time)
 *   utterance_sent → response_received    (HiveMind roundtrip)
 *   tts_started → tts_completed           (speech synthesis duration)
 *
 * Metrics are available via getMetrics() and logged to the console
 * in development mode via toConsoleLog().
 */

// ── Types ──────────────────────────────────────────────

export interface VoiceMetrics {
  /** Time from wake word detection to STT start (ms), or null. */
  wakeWordDetectionMs: number | null;
  /** Time from STT start to final transcript (ms), or null. */
  sttDurationMs: number | null;
  /** Time from utterance sent to speak response received (ms), or null. */
  hivemindRoundtripMs: number | null;
  /** Time from TTS start to audio complete (ms), or null. */
  ttsDurationMs: number | null;
  /** Total pipeline time from first event to last (ms), or null. */
  totalPipelineMs: number | null;
}

/** Well-known pipeline event names for type safety. */
export type VoiceEvent =
  | "wake_word_detected"
  | "stt_started"
  | "stt_completed"
  | "utterance_sent"
  | "response_received"
  | "tts_started"
  | "tts_completed";

// ── Measurement pairs ──────────────────────────────────

interface MeasurementPair {
  from: VoiceEvent;
  to: VoiceEvent;
  key: keyof Omit<VoiceMetrics, "totalPipelineMs">;
}

const MEASUREMENT_PAIRS: readonly MeasurementPair[] = [
  { from: "wake_word_detected", to: "stt_started", key: "wakeWordDetectionMs" },
  { from: "stt_started", to: "stt_completed", key: "sttDurationMs" },
  { from: "utterance_sent", to: "response_received", key: "hivemindRoundtripMs" },
  { from: "tts_started", to: "tts_completed", key: "ttsDurationMs" },
] as const;

// ── Service ────────────────────────────────────────────

export class VoiceMetricsService {
  private timestamps = new Map<VoiceEvent, number>();

  /**
   * Record a high-resolution timestamp for a pipeline event.
   *
   * @param event - The pipeline event to mark.
   */
  mark(event: VoiceEvent): void {
    this.timestamps.set(event, performance.now());
  }

  /**
   * Calculate duration between two recorded events.
   *
   * @param from - Start event name.
   * @param to - End event name.
   * @returns Duration in milliseconds, or null if either event is missing.
   */
  measure(from: VoiceEvent, to: VoiceEvent): number | null {
    const start = this.timestamps.get(from);
    const end = this.timestamps.get(to);

    if (start === undefined || end === undefined) return null;
    return Math.round(end - start);
  }

  /**
   * Compile all pipeline metrics from recorded timestamps.
   *
   * @returns VoiceMetrics with measured durations (null if data missing).
   */
  getMetrics(): VoiceMetrics {
    const metrics: VoiceMetrics = {
      wakeWordDetectionMs: null,
      sttDurationMs: null,
      hivemindRoundtripMs: null,
      ttsDurationMs: null,
      totalPipelineMs: null,
    };

    for (const pair of MEASUREMENT_PAIRS) {
      metrics[pair.key] = this.measure(pair.from, pair.to);
    }

    metrics.totalPipelineMs = this.calculateTotalPipeline();
    return metrics;
  }

  /**
   * Clear all recorded timestamps for the next interaction.
   */
  reset(): void {
    this.timestamps.clear();
  }

  /**
   * Log current metrics to the browser console in a formatted table.
   * Only logs in development mode (non-production).
   */
  toConsoleLog(): void {
    if (
      typeof process !== "undefined" &&
      process.env.NODE_ENV === "production"
    ) {
      return;
    }

    const metrics = this.getMetrics();
    const rows: Array<{ segment: string; ms: string }> = [];

    if (metrics.wakeWordDetectionMs !== null) {
      rows.push({
        segment: "Wake word → STT start",
        ms: `${metrics.wakeWordDetectionMs}ms`,
      });
    }
    if (metrics.sttDurationMs !== null) {
      rows.push({
        segment: "STT transcription",
        ms: `${metrics.sttDurationMs}ms`,
      });
    }
    if (metrics.hivemindRoundtripMs !== null) {
      rows.push({
        segment: "HiveMind roundtrip",
        ms: `${metrics.hivemindRoundtripMs}ms`,
      });
    }
    if (metrics.ttsDurationMs !== null) {
      rows.push({
        segment: "TTS synthesis",
        ms: `${metrics.ttsDurationMs}ms`,
      });
    }
    if (metrics.totalPipelineMs !== null) {
      rows.push({
        segment: "TOTAL PIPELINE",
        ms: `${metrics.totalPipelineMs}ms`,
      });
    }

    if (rows.length > 0) {
      console.groupCollapsed("[AVAROS] Voice Pipeline Metrics");
      console.table(rows);
      console.groupEnd();
    }
  }

  /**
   * Check whether any timestamps have been recorded.
   *
   * @returns True if at least one event has been marked.
   */
  hasData(): boolean {
    return this.timestamps.size > 0;
  }

  // ── Private ──────────────────────────────────────────

  private calculateTotalPipeline(): number | null {
    if (this.timestamps.size < 2) return null;

    const values = Array.from(this.timestamps.values());
    const earliest = Math.min(...values);
    const latest = Math.max(...values);

    return Math.round(latest - earliest);
  }
}
