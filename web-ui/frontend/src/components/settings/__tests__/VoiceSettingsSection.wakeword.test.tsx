// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import VoiceSettingsSection from "../VoiceSettingsSection";

const mockVoice = vi.hoisted(() => ({
  voiceMode: "push-to-talk" as string,
  setVoiceMode: vi.fn().mockResolvedValue(undefined),
  wakeWordState: "idle" as string,
  wakeWordLabel: "Hey Avaros",
  setWakeWordSensitivity: vi.fn(),
  isModelLoading: false,
  setLanguage: vi.fn(),
  availableVoices: [] as SpeechSynthesisVoice[],
  setTTSVoice: vi.fn(),
  ttsSupported: true,
  speak: vi.fn().mockResolvedValue(undefined),
  stopSpeaking: vi.fn(),
  ttsRate: 1,
  setTTSRate: vi.fn(),
  ttsVolume: 1,
  setTTSVolume: vi.fn(),
  requestMicPermission: vi.fn().mockResolvedValue("granted"),
}));

const mockSettings = vi.hoisted(() => ({
  voiceMode: "push-to-talk" as string,
  wakeWordEnabled: false,
  wakeWordSensitivity: 0.5,
  wakeWordUrl: "",
  language: "en-US",
  sttEngine: "browser",
  ttsEngine: "browser",
  ttsVoice: "",
  ttsRate: 1,
  ttsVolume: 1,
  updateSetting: vi.fn(),
  resetDefaults: vi.fn(),
}));

vi.mock("../../../contexts/VoiceContext", () => ({
  useVoice: () => mockVoice,
}));

vi.mock("../../../hooks/useVoiceSettings", () => ({
  DEFAULT_VOICE_SETTINGS: {
    voiceMode: "push-to-talk",
    wakeWordEnabled: false,
    wakeWordSensitivity: 0.5,
    wakeWordUrl: "",
    language: "en-US",
    sttEngine: "browser",
    ttsEngine: "browser",
    ttsVoice: "",
    ttsRate: 1,
    ttsVolume: 1,
  },
  useVoiceSettings: () => mockSettings,
}));

vi.mock("../MicrophoneTest", () => ({
  default: () => <div data-testid="mic-test">MicrophoneTest</div>,
}));

describe("VoiceSettingsSection — wake word panel", () => {
  const onNotify = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockVoice.voiceMode = "push-to-talk";
    mockVoice.wakeWordState = "idle";
    mockVoice.isModelLoading = false;
    mockSettings.wakeWordEnabled = false;
    mockSettings.wakeWordUrl = "";
    mockSettings.wakeWordSensitivity = 0.5;
  });

  afterEach(cleanup);

  it("test_shows_disabled_status_when_wakeword_off", () => {
    render(<VoiceSettingsSection onNotify={onNotify} />);

    expect(screen.getByText("Service disabled")).toBeTruthy();
  });

  it("test_shows_connected_status_when_listening", () => {
    mockSettings.wakeWordEnabled = true;
    mockVoice.wakeWordState = "listening";

    render(<VoiceSettingsSection onNotify={onNotify} />);

    expect(screen.getByText("Connected ✓")).toBeTruthy();
  });

  it("test_shows_connection_failed_on_error_state", () => {
    mockSettings.wakeWordEnabled = true;
    mockVoice.wakeWordState = "error";

    render(<VoiceSettingsSection onNotify={onNotify} />);

    expect(screen.getByText("Connection failed")).toBeTruthy();
  });

  it("test_shows_connecting_when_model_loading", () => {
    mockSettings.wakeWordEnabled = true;
    mockVoice.isModelLoading = true;

    render(<VoiceSettingsSection onNotify={onNotify} />);

    expect(screen.getByText("Connecting...")).toBeTruthy();
  });

  it("test_connection_dot_green_when_connected", () => {
    mockSettings.wakeWordEnabled = true;
    mockVoice.wakeWordState = "listening";

    render(<VoiceSettingsSection onNotify={onNotify} />);

    const dot = screen.getByTitle("Connected");
    expect(dot.className).toContain("bg-emerald-500");
  });

  it("test_connection_dot_red_when_enabled_but_disconnected", () => {
    mockSettings.wakeWordEnabled = true;
    mockVoice.wakeWordState = "error";

    render(<VoiceSettingsSection onNotify={onNotify} />);

    const dot = screen.getByTitle("Disconnected");
    expect(dot.className).toContain("bg-red-500");
  });

  it("test_connection_dot_gray_when_disabled", () => {
    mockSettings.wakeWordEnabled = false;

    render(<VoiceSettingsSection onNotify={onNotify} />);

    const dot = screen.getByTitle("Disconnected");
    expect(dot.className).toContain("bg-slate-400");
  });

  it("test_renders_service_url_input", () => {
    mockSettings.wakeWordEnabled = true;

    render(<VoiceSettingsSection onNotify={onNotify} />);

    const urlInput = screen.getByPlaceholderText("ws://localhost:9999/ws/detect");
    expect(urlInput).toBeTruthy();
    expect((urlInput as HTMLInputElement).disabled).toBe(false);
  });

  it("test_service_url_disabled_when_wakeword_off", () => {
    mockSettings.wakeWordEnabled = false;

    render(<VoiceSettingsSection onNotify={onNotify} />);

    const urlInput = screen.getByPlaceholderText("ws://localhost:9999/ws/detect");
    expect((urlInput as HTMLInputElement).disabled).toBe(true);
  });

  it("test_service_url_shows_saved_value", () => {
    mockSettings.wakeWordEnabled = true;
    mockSettings.wakeWordUrl = "ws://custom:8080/ws/detect";

    render(<VoiceSettingsSection onNotify={onNotify} />);

    const urlInput = screen.getByPlaceholderText(
      "ws://localhost:9999/ws/detect",
    ) as HTMLInputElement;
    expect(urlInput.value).toBe("ws://custom:8080/ws/detect");
  });

  it("test_shows_service_not_available_for_unsupported", () => {
    mockSettings.wakeWordEnabled = true;
    mockVoice.wakeWordState = "unsupported";

    render(<VoiceSettingsSection onNotify={onNotify} />);

    expect(screen.getByText("Service not available")).toBeTruthy();
  });
});
