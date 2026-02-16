/**
 * Unit tests for the VoiceMetricsService.
 *
 * Validates timestamp recording, duration measurement, metrics
 * compilation, reset behaviour, and console logging.
 */

// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  VoiceMetricsService,
  type VoiceEvent,
  type VoiceMetrics,
} from "../voice-metrics";

// ── Helpers ────────────────────────────────────────────

function advancePerformanceNow(service: VoiceMetricsService, events: Array<[VoiceEvent, number]>): void {
  for (const [event, time] of events) {
    vi.spyOn(performance, "now").mockReturnValue(time);
    service.mark(event);
  }
}

// ── Tests ──────────────────────────────────────────────

describe("VoiceMetricsService", () => {
  let service: VoiceMetricsService;

  beforeEach(() => {
    service = new VoiceMetricsService();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("mark", () => {
    it("records a timestamp for a given event", () => {
      vi.spyOn(performance, "now").mockReturnValue(100);
      service.mark("stt_started");

      expect(service.hasData()).toBe(true);
    });

    it("overwrites previous timestamp for the same event", () => {
      vi.spyOn(performance, "now").mockReturnValue(100);
      service.mark("stt_started");

      vi.spyOn(performance, "now").mockReturnValue(200);
      service.mark("stt_started");

      vi.spyOn(performance, "now").mockReturnValue(300);
      service.mark("stt_completed");

      // Should measure from 200, not 100
      expect(service.measure("stt_started", "stt_completed")).toBe(100);
    });
  });

  describe("measure", () => {
    it("returns duration between two events in ms", () => {
      advancePerformanceNow(service, [
        ["stt_started", 1000],
        ["stt_completed", 1500],
      ]);

      expect(service.measure("stt_started", "stt_completed")).toBe(500);
    });

    it("returns null when start event is missing", () => {
      vi.spyOn(performance, "now").mockReturnValue(1500);
      service.mark("stt_completed");

      expect(service.measure("stt_started", "stt_completed")).toBeNull();
    });

    it("returns null when end event is missing", () => {
      vi.spyOn(performance, "now").mockReturnValue(1000);
      service.mark("stt_started");

      expect(service.measure("stt_started", "stt_completed")).toBeNull();
    });

    it("returns null when both events are missing", () => {
      expect(service.measure("stt_started", "stt_completed")).toBeNull();
    });

    it("rounds results to whole milliseconds", () => {
      advancePerformanceNow(service, [
        ["utterance_sent", 100.3],
        ["response_received", 250.7],
      ]);

      expect(service.measure("utterance_sent", "response_received")).toBe(150);
    });
  });

  describe("getMetrics", () => {
    it("returns all null when no events recorded", () => {
      const metrics = service.getMetrics();

      expect(metrics.wakeWordDetectionMs).toBeNull();
      expect(metrics.sttDurationMs).toBeNull();
      expect(metrics.hivemindRoundtripMs).toBeNull();
      expect(metrics.ttsDurationMs).toBeNull();
      expect(metrics.totalPipelineMs).toBeNull();
    });

    it("calculates wake word detection duration", () => {
      advancePerformanceNow(service, [
        ["wake_word_detected", 100],
        ["stt_started", 250],
      ]);

      expect(service.getMetrics().wakeWordDetectionMs).toBe(150);
    });

    it("calculates STT duration", () => {
      advancePerformanceNow(service, [
        ["stt_started", 200],
        ["stt_completed", 1200],
      ]);

      expect(service.getMetrics().sttDurationMs).toBe(1000);
    });

    it("calculates HiveMind roundtrip duration", () => {
      advancePerformanceNow(service, [
        ["utterance_sent", 300],
        ["response_received", 800],
      ]);

      expect(service.getMetrics().hivemindRoundtripMs).toBe(500);
    });

    it("calculates TTS duration", () => {
      advancePerformanceNow(service, [
        ["tts_started", 900],
        ["tts_completed", 2400],
      ]);

      expect(service.getMetrics().ttsDurationMs).toBe(1500);
    });

    it("calculates total pipeline from earliest to latest event", () => {
      advancePerformanceNow(service, [
        ["wake_word_detected", 100],
        ["stt_started", 250],
        ["stt_completed", 1200],
        ["utterance_sent", 1210],
        ["response_received", 1800],
        ["tts_started", 1810],
        ["tts_completed", 3200],
      ]);

      const metrics = service.getMetrics();
      expect(metrics.totalPipelineMs).toBe(3100); // 3200 - 100
    });

    it("returns partial metrics when only some events recorded", () => {
      advancePerformanceNow(service, [
        ["utterance_sent", 500],
        ["response_received", 1000],
      ]);

      const metrics = service.getMetrics();
      expect(metrics.wakeWordDetectionMs).toBeNull();
      expect(metrics.sttDurationMs).toBeNull();
      expect(metrics.hivemindRoundtripMs).toBe(500);
      expect(metrics.ttsDurationMs).toBeNull();
      expect(metrics.totalPipelineMs).toBe(500);
    });
  });

  describe("reset", () => {
    it("clears all recorded timestamps", () => {
      advancePerformanceNow(service, [
        ["stt_started", 100],
        ["stt_completed", 200],
      ]);

      service.reset();

      expect(service.hasData()).toBe(false);
      expect(service.getMetrics().sttDurationMs).toBeNull();
    });
  });

  describe("hasData", () => {
    it("returns false when no events recorded", () => {
      expect(service.hasData()).toBe(false);
    });

    it("returns true after marking an event", () => {
      vi.spyOn(performance, "now").mockReturnValue(100);
      service.mark("stt_started");

      expect(service.hasData()).toBe(true);
    });

    it("returns false after reset", () => {
      vi.spyOn(performance, "now").mockReturnValue(100);
      service.mark("stt_started");
      service.reset();

      expect(service.hasData()).toBe(false);
    });
  });

  describe("toConsoleLog", () => {
    it("logs metrics table to console in dev mode", () => {
      advancePerformanceNow(service, [
        ["utterance_sent", 100],
        ["response_received", 600],
      ]);

      const groupSpy = vi.spyOn(console, "groupCollapsed").mockImplementation(() => {});
      const tableSpy = vi.spyOn(console, "table").mockImplementation(() => {});
      const endSpy = vi.spyOn(console, "groupEnd").mockImplementation(() => {});

      service.toConsoleLog();

      expect(groupSpy).toHaveBeenCalledWith("[AVAROS] Voice Pipeline Metrics");
      expect(tableSpy).toHaveBeenCalledTimes(1);
      expect(endSpy).toHaveBeenCalledTimes(1);
    });

    it("does not log when no data is recorded", () => {
      const groupSpy = vi.spyOn(console, "groupCollapsed").mockImplementation(() => {});

      service.toConsoleLog();

      expect(groupSpy).not.toHaveBeenCalled();
    });
  });
});
