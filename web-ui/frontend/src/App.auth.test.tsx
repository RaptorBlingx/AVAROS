// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";

import App from "./App";

const apiMocks = vi.hoisted(() => ({
  getStoredApiKey: vi.fn<() => string>(),
  getStatus: vi.fn<() => Promise<unknown>>(),
  setStoredApiKey: vi.fn<(key: string) => void>(),
  clearStoredApiKey: vi.fn<() => void>(),
}));

vi.mock("./api/client", () => {
  class MockApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }

  return {
    ApiError: MockApiError,
    clearStoredApiKey: apiMocks.clearStoredApiKey,
    getStatus: apiMocks.getStatus,
    getStoredApiKey: apiMocks.getStoredApiKey,
    setStoredApiKey: apiMocks.setStoredApiKey,
  };
});

vi.mock("./components/common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

vi.mock("./components/common/ErrorBoundary", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("./components/Sidebar", () => ({
  default: () => <div data-testid="sidebar" />,
}));

vi.mock("./components/voice/VoiceWidget", () => ({
  default: () => <div data-testid="voice-widget" />,
}));

vi.mock("./contexts/HiveMindContext", () => ({
  HiveMindProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="hivemind-provider">{children}</div>
  ),
}));

vi.mock("./contexts/VoiceContext", () => ({
  VoiceProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="voice-provider">{children}</div>
  ),
}));

vi.mock("./pages/Dashboard", () => ({
  default: () => <div data-testid="dashboard" />,
}));

vi.mock("./pages/KPIDashboard", () => ({
  default: () => <div data-testid="kpi-dashboard" />,
}));

vi.mock("./pages/ProductionData", () => ({
  default: () => <div data-testid="production-data" />,
}));

vi.mock("./pages/Settings", () => ({
  default: () => <div data-testid="settings" />,
}));

vi.mock("./pages/Wizard", () => ({
  default: () => <div data-testid="wizard" />,
}));

describe("App authentication gating", () => {
  beforeEach(() => {
    apiMocks.getStoredApiKey.mockReset();
    apiMocks.getStatus.mockReset();
    apiMocks.setStoredApiKey.mockReset();
    apiMocks.clearStoredApiKey.mockReset();
    apiMocks.getStoredApiKey.mockReturnValue("");
  });

  it("does not mount voice providers before authentication", async () => {
    render(<App />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "AVAROS" }),
      ).toBeTruthy();
    });

    expect(screen.queryByTestId("hivemind-provider")).toBeNull();
    expect(screen.queryByTestId("voice-provider")).toBeNull();
    expect(apiMocks.getStatus).not.toHaveBeenCalled();
  });

  it("mounts voice providers after successful sign in", async () => {
    apiMocks.getStatus.mockResolvedValue({ configured: true });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByLabelText("API Key")).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("API Key"), {
      target: { value: "raptorblingx" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(screen.getByTestId("hivemind-provider")).toBeTruthy();
    });

    expect(screen.getByTestId("voice-provider")).toBeTruthy();
    expect(apiMocks.setStoredApiKey).toHaveBeenCalledWith("raptorblingx");
    expect(apiMocks.getStatus).toHaveBeenCalledTimes(1);
  });
});