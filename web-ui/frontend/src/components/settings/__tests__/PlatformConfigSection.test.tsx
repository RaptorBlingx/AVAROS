// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockApi = vi.hoisted(() => ({
  createPlatformConfig: vi.fn(),
  getProfile: vi.fn(),
  getPlatformConfig: vi.fn(),
  resetPlatformConfig: vi.fn(),
  testConnection: vi.fn(),
  listProfiles: vi.fn(),
  activateProfile: vi.fn(),
  createProfile: vi.fn(),
  deleteProfile: vi.fn(),
  toFriendlyErrorMessage: vi.fn((error: unknown) =>
    error instanceof Error ? error.message : "Unknown error",
  ),
}));

vi.mock("../../../api/client", () => mockApi);

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import PlatformConfigSection from "../PlatformConfigSection";

function resetMocks(): void {
  mockApi.createPlatformConfig.mockReset();
  mockApi.getProfile.mockReset();
  mockApi.getPlatformConfig.mockReset();
  mockApi.resetPlatformConfig.mockReset();
  mockApi.testConnection.mockReset();
  mockApi.listProfiles.mockReset();
  mockApi.activateProfile.mockReset();
  mockApi.createProfile.mockReset();
  mockApi.deleteProfile.mockReset();

  mockApi.getPlatformConfig.mockResolvedValue({
    platform_type: "mock",
    api_url: "",
    api_key: "****",
    extra_settings: { auth_type: "bearer" },
  });

  mockApi.listProfiles.mockResolvedValue({
    active_profile: "mock",
    profiles: [
      { name: "mock", platform_type: "mock", is_builtin: true, is_active: true },
      {
        name: "staging",
        platform_type: "reneryo",
        is_builtin: false,
        is_active: false,
      },
    ],
  });

  mockApi.getProfile.mockImplementation(async (name: string) => {
    if (name === "staging") {
      return {
        name: "staging",
        platform_type: "reneryo",
        api_url: "https://staging.example.com",
        api_key: "****1234",
        extra_settings: { auth_type: "cookie" },
        is_builtin: false,
        is_active: false,
      };
    }
    return {
      name: "mock",
      platform_type: "mock",
      api_url: "",
      api_key: "****",
      extra_settings: { auth_type: "bearer" },
      is_builtin: true,
      is_active: true,
    };
  });
}

describe("PlatformConfigSection", () => {
  beforeEach(() => {
    resetMocks();
  });

  it("updates form values when profile selection changes", async () => {
    render(<PlatformConfigSection onNotify={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    const profileDropdown = screen.getByTestId("profile-dropdown");
    fireEvent.change(profileDropdown, {
      target: { value: "staging" },
    });

    await waitFor(() => {
      expect(mockApi.getProfile).toHaveBeenCalledWith("staging");
    });

    await waitFor(() => {
      const apiUrlInput = screen.getByLabelText("API URL") as HTMLInputElement;
      expect(apiUrlInput.value).toBe("https://staging.example.com");
    });

    await waitFor(() => {
      expect(screen.getByText("Session Cookie Value")).toBeTruthy();
    });
  });
});
