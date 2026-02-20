// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ProfileConfig, ProfileListResponse } from "../../../api/types";
import type { ProfileSelectorProps } from "../ProfileSelector";
import ProfileSelector from "../ProfileSelector";

vi.mock("../../../api/client", () => ({
  listProfiles: vi.fn(),
  getProfile: vi.fn(),
  createProfile: vi.fn(),
  deleteProfile: vi.fn(),
  activateProfile: vi.fn(),
  toFriendlyErrorMessage: vi.fn((e: unknown) => String(e)),
}));

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import {
  activateProfile,
  createProfile,
  deleteProfile,
  getProfile,
  listProfiles,
} from "../../../api/client";

const mockListProfiles = vi.mocked(listProfiles);
const mockGetProfile = vi.mocked(getProfile);
const mockCreateProfile = vi.mocked(createProfile);
const mockDeleteProfile = vi.mocked(deleteProfile);
const mockActivateProfile = vi.mocked(activateProfile);

const MOCK_PROFILES: ProfileListResponse = {
  profiles: [
    {
      name: "mock",
      platform_type: "mock",
      is_active: true,
      is_builtin: true,
    },
    {
      name: "my-reneryo",
      platform_type: "reneryo",
      is_active: false,
      is_builtin: false,
    },
  ],
  active_profile: "mock",
};

const MOCK_PROFILE_CONFIG: ProfileConfig = {
  name: "mock",
  platform_type: "mock",
  api_url: "",
  api_key: "****",
  extra_settings: {},
  is_builtin: true,
  is_active: true,
};

const RENERYO_PROFILE_CONFIG: ProfileConfig = {
  name: "my-reneryo",
  platform_type: "reneryo",
  api_url: "https://api.reneryo.com",
  api_key: "****abcd",
  extra_settings: { auth_type: "bearer" },
  is_builtin: false,
  is_active: false,
};

describe("ProfileSelector", () => {
  let onProfileChange: ProfileSelectorProps["onProfileChange"] &
    ReturnType<typeof vi.fn>;
  let onNotify: ProfileSelectorProps["onNotify"] & ReturnType<typeof vi.fn>;

  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    onProfileChange = vi.fn() as typeof onProfileChange;
    onNotify = vi.fn() as typeof onNotify;
    mockListProfiles.mockResolvedValue(MOCK_PROFILES);
    mockGetProfile.mockImplementation(async (name: string) => {
      if (name === "mock") return MOCK_PROFILE_CONFIG;
      if (name === "my-reneryo") return RENERYO_PROFILE_CONFIG;
      throw new Error(`Unknown profile: ${name}`);
    });
  });

  it("renders profiles after loading", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    const dropdown = screen.getByTestId(
      "profile-dropdown",
    ) as HTMLSelectElement;
    expect(dropdown.options.length).toBe(2);
  });

  it("shows mock profile first with built-in label", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    const dropdown = screen.getByTestId(
      "profile-dropdown",
    ) as HTMLSelectElement;
    const firstOption = dropdown.options[0];
    expect(firstOption.value).toBe("mock");
    expect(firstOption.text).toContain("Built-in");
  });

  it("shows active badge for the active profile", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("badge-active")).toBeTruthy();
    });
  });

  it("shows built-in badge for mock profile", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("badge-builtin")).toBeTruthy();
    });
  });

  it("disables switch button for the currently active profile", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-switch-btn")).toBeTruthy();
    });

    const switchBtn = screen.getByTestId(
      "profile-switch-btn",
    ) as HTMLButtonElement;
    expect(switchBtn.disabled).toBe(true);
  });

  it("calls getProfile and onProfileChange when selecting a different profile", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    const dropdown = screen.getByTestId(
      "profile-dropdown",
    ) as HTMLSelectElement;
    fireEvent.change(dropdown, { target: { value: "my-reneryo" } });

    await waitFor(() => {
      expect(mockGetProfile).toHaveBeenCalledWith("my-reneryo");
      expect(onProfileChange).toHaveBeenCalledWith(RENERYO_PROFILE_CONFIG);
    });
  });

  it("calls activateProfile on switch and notifies success", async () => {
    const activatedConfig: ProfileConfig = {
      ...RENERYO_PROFILE_CONFIG,
      is_active: true,
    };
    mockActivateProfile.mockResolvedValue(activatedConfig);

    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    const dropdown = screen.getByTestId(
      "profile-dropdown",
    ) as HTMLSelectElement;
    fireEvent.change(dropdown, { target: { value: "my-reneryo" } });

    await waitFor(() => {
      expect(onProfileChange).toHaveBeenCalled();
    });

    const switchBtn = screen.getByTestId(
      "profile-switch-btn",
    ) as HTMLButtonElement;
    expect(switchBtn.disabled).toBe(false);

    fireEvent.click(switchBtn);

    await waitFor(() => {
      expect(mockActivateProfile).toHaveBeenCalledWith("my-reneryo");
      expect(onNotify).toHaveBeenCalledWith(
        "success",
        expect.stringContaining("my-reneryo"),
      );
    });
  });

  it("does not show delete button for built-in mock profile", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    expect(screen.queryByTestId("profile-delete-btn")).toBeNull();
  });

  it("shows delete button for custom profile", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    const dropdown = screen.getByTestId(
      "profile-dropdown",
    ) as HTMLSelectElement;
    fireEvent.change(dropdown, { target: { value: "my-reneryo" } });

    await waitFor(() => {
      expect(screen.getByTestId("profile-delete-btn")).toBeTruthy();
    });
  });

  it("calls deleteProfile with confirmation on delete", async () => {
    mockDeleteProfile.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    const dropdown = screen.getByTestId(
      "profile-dropdown",
    ) as HTMLSelectElement;
    fireEvent.change(dropdown, { target: { value: "my-reneryo" } });

    await waitFor(() => {
      expect(screen.getByTestId("profile-delete-btn")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("profile-delete-btn"));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
      expect(mockDeleteProfile).toHaveBeenCalledWith("my-reneryo");
      expect(onNotify).toHaveBeenCalledWith(
        "success",
        expect.stringContaining("my-reneryo"),
      );
    });

    vi.mocked(window.confirm).mockRestore();
  });

  it("does not delete if user cancels confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    fireEvent.change(screen.getByTestId("profile-dropdown"), {
      target: { value: "my-reneryo" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("profile-delete-btn")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("profile-delete-btn"));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
    });

    expect(mockDeleteProfile).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockRestore();
  });

  it("shows new profile form when clicking New Profile", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-new-btn")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("profile-new-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("new-profile-form")).toBeTruthy();
    });
  });

  it("validates profile name on create", async () => {
    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-new-btn")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("profile-new-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("profile-create-btn")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("profile-create-btn"));

    await waitFor(() => {
      expect(onNotify).toHaveBeenCalledWith(
        "error",
        expect.stringContaining("2"),
      );
    });

    expect(mockCreateProfile).not.toHaveBeenCalled();
  });

  it("creates profile with valid name", async () => {
    const newConfig: ProfileConfig = {
      name: "new-profile",
      platform_type: "reneryo",
      api_url: "",
      api_key: "",
      extra_settings: {},
      is_builtin: false,
      is_active: false,
    };
    mockCreateProfile.mockResolvedValue(newConfig);
    mockGetProfile.mockImplementation(async (name: string) => {
      if (name === "new-profile") return newConfig;
      if (name === "mock") return MOCK_PROFILE_CONFIG;
      return RENERYO_PROFILE_CONFIG;
    });

    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-new-btn")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("profile-new-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("profile-new-name")).toBeTruthy();
    });

    fireEvent.change(screen.getByTestId("profile-new-name"), {
      target: { value: "new-profile" },
    });

    fireEvent.click(screen.getByTestId("profile-create-btn"));

    await waitFor(() => {
      expect(mockCreateProfile).toHaveBeenCalledWith({
        name: "new-profile",
        platform_type: "reneryo",
      });
      expect(onNotify).toHaveBeenCalledWith(
        "success",
        expect.stringContaining("new-profile"),
      );
    });
  });

  it("returns null when no profiles are loaded and not loading", async () => {
    mockListProfiles.mockResolvedValue({
      profiles: [],
      active_profile: "",
    });

    const { container } = render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(
        container.querySelector("[data-testid='profile-selector-loading']"),
      ).toBeNull();
    });

    expect(
      container.querySelector("[data-testid='profile-selector-section']"),
    ).toBeNull();
  });

  it("handles API error gracefully on load", async () => {
    mockListProfiles.mockRejectedValue(new Error("Network error"));

    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(onNotify).toHaveBeenCalledWith("error", expect.any(String));
    });
  });

  it("handles switch failure without changing UI state", async () => {
    mockActivateProfile.mockRejectedValue(new Error("Connection error"));

    render(
      <ProfileSelector onProfileChange={onProfileChange} onNotify={onNotify} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    fireEvent.change(screen.getByTestId("profile-dropdown"), {
      target: { value: "my-reneryo" },
    });

    await waitFor(() => {
      expect(onProfileChange).toHaveBeenCalledWith(RENERYO_PROFILE_CONFIG);
    });

    onNotify.mockClear();

    fireEvent.click(screen.getByTestId("profile-switch-btn"));

    await waitFor(() => {
      expect(onNotify).toHaveBeenCalledWith("error", expect.any(String));
    });

    const dropdown = screen.getByTestId(
      "profile-dropdown",
    ) as HTMLSelectElement;
    expect(dropdown.value).toBe("my-reneryo");
  });
});
