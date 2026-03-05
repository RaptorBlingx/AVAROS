// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useWakeWord } from "../useWakeWord";

const mockState = vi.hoisted(() => {
  const backendWakeWordInstance = {
    onStateChange: vi.fn().mockReturnValue(() => {}),
    onDetected: vi.fn().mockReturnValue(() => {}),
    setSensitivity: vi.fn(),
    dispose: vi.fn(),
  };

  const voiceModeInstance = {
    setMode: vi.fn().mockResolvedValue(undefined),
  };

  return {
    backendWakeWordInstance,
    backendWakeWordCtor: vi.fn(),
    voiceModeInstance,
    voiceModeCtor: vi.fn(),
  };
});

vi.mock("../../services/wake-word-backend", () => ({
  BackendWakeWordService: class MockBackendWakeWordService {
    constructor(...args: unknown[]) {
      mockState.backendWakeWordCtor(...args);
      return mockState.backendWakeWordInstance;
    }
  },
}));

vi.mock("../../services/voice-mode", () => ({
  VoiceModeService: class MockVoiceModeService {
    private _mode = "text";

    constructor(...args: unknown[]) {
      mockState.voiceModeCtor(...args);
    }

    async setMode(mode: string): Promise<string> {
      await mockState.voiceModeInstance.setMode(mode);
      this._mode = mode;
      return mode;
    }

    getMode(): string {
      return this._mode;
    }

    isUsingBackend(): boolean {
      return false;
    }
  },
}));

describe("useWakeWord", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    mockState.backendWakeWordInstance.onStateChange.mockReturnValue(() => {});
    mockState.backendWakeWordInstance.onDetected.mockReturnValue(() => {});
    mockState.voiceModeInstance.setMode.mockResolvedValue(undefined);
  });

  it("test_initializes_backend_wake_word_service", () => {
    const sttRef = { current: null as null | { setContinuous: (value: boolean) => void; stop: () => void } };

    renderHook(() =>
      useWakeWord({
        sttRef: sttRef as never,
        onDetected: vi.fn(),
      }),
    );

    expect(mockState.backendWakeWordCtor).toHaveBeenCalledTimes(1);
  });

  it("test_uses_persisted_wake_word_url_for_backend_constructor", () => {
    window.localStorage.setItem(
      "avaros_wake_word_url",
      "ws://wakeword.internal:9999/ws/detect",
    );

    const sttRef = { current: null as null | { setContinuous: (value: boolean) => void; stop: () => void } };

    renderHook(() =>
      useWakeWord({
        sttRef: sttRef as never,
        onDetected: vi.fn(),
      }),
    );

    expect(mockState.backendWakeWordCtor).toHaveBeenCalledWith({
      wsUrl: "ws://wakeword.internal:9999/ws/detect",
    });
  });

  it("test_set_voice_mode_after_late_stt_init_activates_wake_word", async () => {
    const sttStop = vi.fn();
    const sttRef = { current: null as null | { setContinuous: (value: boolean) => void; stop: () => void } };

    const { result } = renderHook(() =>
      useWakeWord({
        sttRef: sttRef as never,
        onDetected: vi.fn(),
      }),
    );

    expect(mockState.voiceModeCtor).not.toHaveBeenCalled();

    sttRef.current = { setContinuous: vi.fn(), stop: sttStop };

    await act(async () => {
      await result.current.setVoiceMode("wake-word");
    });

    expect(mockState.voiceModeCtor).toHaveBeenCalledTimes(1);
    expect(mockState.voiceModeInstance.setMode).toHaveBeenCalledWith("wake-word");
    expect(result.current.voiceMode).toBe("wake-word");
    expect(result.current.wakeWordEnabled).toBe(true);
  });

  it("test_set_voice_mode_throws_when_service_not_ready", async () => {
    const sttRef = { current: null };

    const { result } = renderHook(() =>
      useWakeWord({
        sttRef: sttRef as never,
        onDetected: vi.fn(),
      }),
    );

    await expect(
      act(async () => {
        await result.current.setVoiceMode("push-to-talk");
      }),
    ).rejects.toThrow("Voice mode service is not ready");
  });

  it("test_no_fallback_active_property", () => {
    const sttRef = { current: null };

    const { result } = renderHook(() =>
      useWakeWord({
        sttRef: sttRef as never,
        onDetected: vi.fn(),
      }),
    );

    // wakeWordFallbackActive removed in P6-E08
    expect(result.current).not.toHaveProperty("wakeWordFallbackActive");
  });

  it("test_sensitivity_updates_backend_service", () => {
    const sttRef = { current: null };

    const { result } = renderHook(() =>
      useWakeWord({
        sttRef: sttRef as never,
        onDetected: vi.fn(),
      }),
    );

    act(() => {
      result.current.setWakeWordSensitivity(0.9);
    });

    expect(mockState.backendWakeWordInstance.setSensitivity).toHaveBeenCalledWith(0.9);
    expect(result.current.wakeWordSensitivity).toBe(0.9);
  });
});
