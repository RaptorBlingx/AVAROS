// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useWakeWord } from "../useWakeWord";

const mockState = vi.hoisted(() => {
  const wakeWordInstance = {
    onStateChange: vi.fn().mockReturnValue(() => {}),
    onDetected: vi.fn().mockReturnValue(() => {}),
    setSensitivity: vi.fn(),
    dispose: vi.fn().mockResolvedValue(undefined),
  };

  const voiceModeInstance = {
    setMode: vi.fn().mockResolvedValue(undefined),
  };

  return {
    wakeWordInstance,
    wakeWordCtor: vi.fn(),
    voiceModeInstance,
    voiceModeCtor: vi.fn(),
  };
});

vi.mock("../../services/wake-word", () => ({
  WakeWordService: class MockWakeWordService {
    constructor() {
      mockState.wakeWordCtor();
      return mockState.wakeWordInstance;
    }
  },
}));

vi.mock("../../services/voice-mode", () => ({
  VoiceModeService: class MockVoiceModeService {
    constructor(...args: unknown[]) {
      mockState.voiceModeCtor(...args);
    }

    setMode(mode: string): Promise<void> {
      return mockState.voiceModeInstance.setMode(mode);
    }
  },
}));

describe("useWakeWord", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockState.wakeWordInstance.onStateChange.mockReturnValue(() => {});
    mockState.wakeWordInstance.onDetected.mockReturnValue(() => {});
    mockState.voiceModeInstance.setMode.mockResolvedValue(undefined);
  });

  it("test_set_voice_mode_after_late_stt_init_activates_wake_word", async () => {
    const sttSetContinuous = vi.fn();
    const sttRef = { current: null as null | { setContinuous: (value: boolean) => void } };

    const { result } = renderHook(() =>
      useWakeWord({
        sttRef: sttRef as never,
        onDetected: vi.fn(),
      }),
    );

    expect(mockState.voiceModeCtor).not.toHaveBeenCalled();

    sttRef.current = { setContinuous: sttSetContinuous };

    await act(async () => {
      await result.current.setVoiceMode("wake-word");
    });

    expect(mockState.voiceModeCtor).toHaveBeenCalledTimes(1);
    expect(mockState.voiceModeInstance.setMode).toHaveBeenCalledWith("wake-word");
    expect(sttSetContinuous).toHaveBeenCalledWith(true);
    expect(result.current.voiceMode).toBe("wake-word");
    expect(result.current.wakeWordEnabled).toBe(true);
  });
});
