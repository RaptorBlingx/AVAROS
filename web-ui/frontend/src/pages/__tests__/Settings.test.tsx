// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mockNavigate = vi.fn();

vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("../../components/common/OnboardingOverlay", () => ({
  default: () => null,
}));

vi.mock("../../components/common/Tooltip", () => ({
  default: () => null,
}));

vi.mock("../../components/common/Toast", () => ({
  default: ({
    toasts,
  }: {
    toasts: Array<{ id: number; type: string; message: string }>;
  }) => (
    <div data-testid="toast-root">
      {toasts.map((toast) => (
        <p key={toast.id}>{toast.message}</p>
      ))}
    </div>
  ),
}));

vi.mock("../../components/settings/SystemInfoSection", () => ({
  default: () => null,
}));

vi.mock("../../components/settings/MetricMappingsSection", () => ({
  default: ({ refreshKey }: { refreshKey?: number }) => (
    <div data-testid="metrics-refresh">{refreshKey ?? 0}</div>
  ),
}));

vi.mock("../../components/settings/IntentBindingsSection", () => ({
  default: ({ refreshKey }: { refreshKey?: number }) => (
    <div data-testid="intent-bindings-refresh">{refreshKey ?? 0}</div>
  ),
}));

vi.mock("../../components/settings/EmissionFactorsSection", () => ({
  default: ({ refreshKey }: { refreshKey?: number }) => (
    <div data-testid="emission-refresh">{refreshKey ?? 0}</div>
  ),
}));

vi.mock("../../components/settings/IntentActivationSection", () => ({
  default: ({ refreshKey }: { refreshKey?: number }) => (
    <div data-testid="intent-refresh">{refreshKey ?? 0}</div>
  ),
}));

vi.mock("../../components/settings/PlatformConfigSection", () => ({
  default: ({
    onProfileSwitch,
  }: {
    onProfileSwitch?: (profileName: string, voiceReloaded: boolean) => void;
  }) => (
    <div>
      <button
        type="button"
        onClick={() => onProfileSwitch?.("reneryo", true)}
      >
        Switch Profile Success
      </button>
      <button
        type="button"
        onClick={() => onProfileSwitch?.("sap", false)}
      >
        Switch Profile Voice Fail
      </button>
    </div>
  ),
}));

import Settings from "../Settings";

describe("Settings page profile refresh", () => {
  it("test_settings_increments_refresh_key_on_profile_switch", () => {
    render(<Settings />);

    expect(screen.getByTestId("metrics-refresh").textContent).toBe("0");
    expect(screen.getByTestId("intent-bindings-refresh").textContent).toBe("0");
    expect(screen.getByTestId("emission-refresh").textContent).toBe("0");
    expect(screen.getByTestId("intent-refresh").textContent).toBe("0");

    fireEvent.click(screen.getByText("Switch Profile Success"));

    expect(screen.getByTestId("metrics-refresh").textContent).toBe("1");
    expect(screen.getByTestId("intent-bindings-refresh").textContent).toBe("1");
    expect(screen.getByTestId("emission-refresh").textContent).toBe("1");
    expect(screen.getByTestId("intent-refresh").textContent).toBe("1");
  });

  it("test_profile_badge_shows_active_name", () => {
    render(<Settings />);

    expect(screen.getByText("Profile: mock")).toBeTruthy();
    fireEvent.click(screen.getByText("Switch Profile Success"));
    expect(screen.getByText("Profile: reneryo")).toBeTruthy();
  });

  it("test_voice_reload_failure_shows_warning", () => {
    render(<Settings />);

    fireEvent.click(screen.getByText("Switch Profile Voice Fail"));

    expect(
      screen.getByText(
        "Voice runtime was not notified — voice queries may use the previous profile until next restart.",
      ),
    ).toBeTruthy();
  });
});
